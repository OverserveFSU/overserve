# PROVENANCE: hand-specified experimental control (detect_bench). Thin OpenAI-compatible proxy in
# front of the local vLLM qwen3.5 endpoint: (1) disables the thinking channel via
# chat_template_kwargs so third-party scanners that read `message.content` get a real answer,
# (2) if content still comes back empty, promotes reasoning_content into content, (3) enforces a
# minimum max_tokens so JSON answers are not truncated. No prompt content is altered.
import json, os, sys, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("LLM_UPSTREAM", "http://127.0.0.1:8192")
PORT = int(os.environ.get("LLM_PROXY_PORT", "8193"))
MIN_MAX_TOKENS = int(os.environ.get("LLM_MIN_MAX_TOKENS", "4096"))


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _fwd(self, method, body=None):
        req = urllib.request.Request(UPSTREAM + self.path, data=body, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

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
            body["max_tokens"] = max(int(body.get("max_tokens") or 0), MIN_MAX_TOKENS)
            body["stream"] = False
            body.pop("stream_options", None)
            body["model"] = "qwen3.5"
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
