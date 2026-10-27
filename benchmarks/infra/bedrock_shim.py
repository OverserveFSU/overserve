# Minimal OpenAI-compatible -> litellm(Bedrock sonnet-5) shim, stdlib only (litellm already installed).
# Exposes POST /v1/chat/completions on 0.0.0.0:8300; forces model=bedrock/us.anthropic.claude-sonnet-5,
# passes through messages/tools/tool_choice/temperature/max_tokens; returns OpenAI-format JSON.
import json, os, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import litellm
litellm.drop_params = True  # sonnet-5 rejects temperature=0/top_p etc.; drop unsupported sampling params

MODEL = os.environ.get("SHIM_MODEL", "bedrock/us.anthropic.claude-sonnet-5")
PORT = int(os.environ.get("SHIM_PORT", "8300"))

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._send(200, {"object": "list", "data": [{"id": MODEL, "object": "model", "owned_by": "bedrock"}]})
        else:
            self._send(200, {"status": "ok"})
    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            self._send(400, {"error": {"message": "bad json: %s" % e}}); return
        kw = {"model": MODEL, "messages": body.get("messages", [])}
        for k in ("tools", "tool_choice", "temperature", "max_tokens", "top_p", "stop", "response_format"):
            if k in body and body[k] is not None:
                kw[k] = body[k]
        kw.setdefault("max_tokens", 4096)
        try:
            r = litellm.completion(**kw)
            out = r.model_dump() if hasattr(r, "model_dump") else json.loads(r.json())
            self._send(200, out)
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"error": {"message": str(e)[:500], "type": "shim_error"}})

if __name__ == "__main__":
    print("bedrock shim: %s on 0.0.0.0:%d" % (MODEL, PORT), flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
