# OpenAI-compatible shim -> LAN qwen3.8 vllm, injecting chat_template_kwargs.enable_thinking=false
# (qwen3.8 defaults to thinking mode -> content=None, which breaks litellm/openai clients).
# Forwards /v1/chat/completions and /v1/models to the LAN server with the real key. stdlib only.
import json, os, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("Q38_UPSTREAM", "http://192.168.122.103:8000/v1")
KEY = open("/tmp/claude-1007/-home-ruiheng-aiagent-saas/4a8df908-2ac5-47ab-8487-83551d48626c/scratchpad/qwen38_key.txt").read().strip()
PORT = int(os.environ.get("Q38_PORT", "8301"))

def _fwd(path, body=None):
    url = UPSTREAM + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read()

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, raw):
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        try: self._send(200, _fwd("/models"))
        except Exception as e: self._send(200, json.dumps({"object":"list","data":[{"id":"qwen3.8-27b","object":"model"}]}).encode())
    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        try: body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            self._send(400, json.dumps({"error": {"message": "bad json: %s" % e}}).encode()); return
        body.setdefault("chat_template_kwargs", {})
        body["chat_template_kwargs"]["enable_thinking"] = False
        try:
            self._send(200, _fwd("/chat/completions", body))
        except urllib.error.HTTPError as e:
            self._send(e.code, e.read())
        except Exception as e:
            self._send(500, json.dumps({"error": {"message": str(e)[:400], "type": "shim_error"}}).encode())

if __name__ == "__main__":
    print("qwen3.8 shim: %s (enable_thinking=false) on 0.0.0.0:%d" % (UPSTREAM, PORT), flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
