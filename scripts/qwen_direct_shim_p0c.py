#!/usr/bin/env python3
"""OpenAI-compatible chat/completions -> DIRECT qwen3.8-27b vLLM shim (P0-c reviewer-rigor).

Replaces the DOWN :8301 qwen shim. MCPMark's agent calls litellm.acompletion(
model="openai/qwen3.8-27b", OPENAI_API_BASE=this shim). The shim:
  * forwards to the direct qwen vLLM endpoint (192.168.122.103:8000) with the real model id,
  * injects chat_template_kwargs={"enable_thinking": false}  (the thing the old :8301 shim did;
    qwen3.8 MUST have thinking disabled or it stalls on empty content),
  * forwards ONLY a safe allowlist of request fields (drops the agent's enforcer_mode/think_mode=on
    so they cannot re-enable thinking), passing temperature/top_p/max_tokens THROUGH verbatim so the
    victim behaves exactly as the agent intends (temperature=1.0 -> reps vary, as designed),
  * content=None safety net: if the assistant turn has no content AND no tool_calls, surface any
    reasoning text so the agent never sees a truly empty turn.

stdlib + urllib only. ONLY the transport is provided; no MCPMark code or attack spec is touched.
Unique port (default 8372) + unique name so it never collides with sibling qwen legs.
"""
import json, os, traceback, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KEY_FILE = os.environ.get("QWEN_KEY_FILE", "/home/ruiheng/aiagent/saas/deepseek_v4flash_key.txt")
KEY = open(KEY_FILE).read().strip()
MODEL = os.environ.get("QWEN_MODEL", "qwen3.8-27b")
PORT = int(os.environ.get("SHIM_PORT", "8372"))
UPSTREAM = os.environ.get("QWEN_UPSTREAM", "http://192.168.122.103:8000/v1/chat/completions")
# fields we forward verbatim (temperature/top_p/max_tokens passed through = faithful to agent)
PASS = ("messages", "tools", "tool_choice", "stop", "response_format",
        "temperature", "top_p", "max_tokens")


def _forward(body):
    req = urllib.request.Request(
        UPSTREAM, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.status, json.load(r)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._send(200, {"object": "list", "data": [{"id": MODEL, "object": "model"}]})
        else:
            self._send(200, {"status": "ok", "model": MODEL})

    def do_POST(self):
        if not self.path.endswith("/chat/completions"):
            self._send(404, {"error": {"message": "unsupported path: " + self.path}})
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            self._send(400, {"error": {"message": "bad json: %s" % e}})
            return
        out = {"model": MODEL}
        for k in PASS:
            if body.get(k) is not None:
                out[k] = body[k]
        # THE qwen thinking-disable injection (old :8301 shim behavior).
        out["chat_template_kwargs"] = {"enable_thinking": False}
        try:
            code, resp = _forward(out)
        except urllib.error.HTTPError as e:
            self._send(e.code, {"error": {"message": e.read().decode()[:600], "type": "upstream_http"}})
            return
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"error": {"message": str(e)[:600], "type": "shim_error"}})
            return
        # content=None safety net
        try:
            for ch in resp.get("choices", []):
                msg = ch.get("message", {})
                if not (msg.get("content") or "").strip() and not msg.get("tool_calls"):
                    rtext = msg.get("reasoning") or msg.get("reasoning_content") or ""
                    if rtext.strip():
                        msg["content"] = rtext
        except Exception:
            traceback.print_exc()
        self._send(code, resp)


if __name__ == "__main__":
    print("qwen DIRECT shim (P0-c): %s -> %s on 0.0.0.0:%d (enable_thinking=false)"
          % (MODEL, UPSTREAM, PORT), flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
