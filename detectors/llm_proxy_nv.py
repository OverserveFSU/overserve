# PROVENANCE: hand-specified experimental control (detectors, NV run). Copy of llm_proxy.py
# pointed at the live LAN victim VM (qwen3.8-27b) instead of the dead local :8192 upstream.
# Differences vs llm_proxy.py:
#   - UPSTREAM defaults to the VM at http://192.168.122.103:8000
#   - injects Authorization: Bearer <key-from-file> on forwarded requests
#   - forces body["model"] = "qwen3.8-27b" (not qwen3.5)
#   - injects chat_template_kwargs={"enable_thinking": false}
# Runs on a UNIQUE port (default 8194). No prompt content is altered.
import json, os, sys, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("LLM_UPSTREAM", "http://192.168.122.103:8000")
PORT = int(os.environ.get("LLM_PROXY_PORT", "8194"))
MIN_MAX_TOKENS = int(os.environ.get("LLM_MIN_MAX_TOKENS", "4096"))
MODEL = os.environ.get("LLM_FORCE_MODEL", "qwen3.8-27b")
UPSTREAM_TIMEOUT = int(os.environ.get("LLM_UPSTREAM_TIMEOUT", "60"))
KEYFILE = os.environ.get("LLM_KEYFILE", "/home/ruiheng/aiagent/saas/deepseek_v4flash_key.txt")
KEY = open(KEYFILE).read().strip()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _fwd(self, method, body=None):
        req = urllib.request.Request(UPSTREAM + self.path, data=body, method=method,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + KEY})
        try:
            with urllib.request.urlopen(req, timeout=UPSTREAM_TIMEOUT) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except Exception as e:
            # upstream timeout / connection error (VM flap): return a fast 504 so the client
            # retries immediately instead of hanging on the socket.
            return 504, json.dumps({"error": {"message": "upstream_unavailable: %s" % e}}).encode()

    def _reply(self, code, data):
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        code, data = self._fwd("GET"); self._reply(code, data)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); raw = self.rfile.read(n) if n else b"{}"
        try: body = json.loads(raw)
        except Exception: body = {}
        if self.path.endswith("/chat/completions") and isinstance(body, dict):
            body.setdefault("chat_template_kwargs", {})["enable_thinking"] = False
            # Hard CAP (not a floor): these detector prompts return compact JSON verdicts; capping
            # generation length bounds per-call latency on the flapping VM. Floor keeps it from being
            # set absurdly low by a caller.
            _cap = int(os.environ.get("LLM_FORCE_MAX_TOKENS", "700"))
            body["max_tokens"] = min(max(int(body.get("max_tokens") or _cap), MIN_MAX_TOKENS), _cap)
            body["stream"] = False
            body.pop("stream_options", None)
            body["model"] = MODEL
            code, data = self._fwd("POST", json.dumps(body).encode())
            try:
                d = json.loads(data)
                for ch in d.get("choices", []):
                    m = ch.get("message", {})
                    if not (m.get("content") or "").strip():
                        rc = m.get("reasoning_content") or m.get("reasoning") or ""
                        if rc: m["content"] = rc
                data = json.dumps(d).encode()
            except Exception:
                pass
            self._reply(code, data); return
        code, data = self._fwd("POST", raw); self._reply(code, data)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
