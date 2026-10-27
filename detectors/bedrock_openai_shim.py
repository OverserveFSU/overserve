# Minimal Bedrock -> OpenAI chat-completions shim so detectors/run_repro.py can use a Bedrock model
# (e.g. us.openai.gpt-6-astra) as the judge unchanged. Accepts POST /v1/chat/completions {model,messages,
# max_tokens}, converts to Bedrock converse (system + user), returns {choices:[{message:{content}}]}.
import json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bedrock_test as BR

REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
MODEL = os.environ.get("BEDROCK_MODEL", "us.openai.gpt-6-astra")
PORT = int(os.environ.get("SHIM_PORT", "8194"))
KEY = BR.load_key()
MIN_TOKENS = int(os.environ.get("SHIM_MIN_TOKENS", "4000"))   # headroom for reasoning models


def converse_text(messages, max_tokens):
    import urllib.request
    sys_txt = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
    usr_txt = "\n\n".join(m["content"] for m in messages if m.get("role") != "system")
    body = {"messages": [{"role": "user", "content": [{"text": usr_txt}]}],
            "inferenceConfig": {"maxTokens": max(int(max_tokens or 1500), MIN_TOKENS)}}
    if sys_txt:
        body["system"] = [{"text": sys_txt}]
    url = "https://bedrock-runtime.%s.amazonaws.com/model/%s/converse" % (REGION, MODEL)
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.load(r)
    blocks = resp.get("output", {}).get("message", {}).get("content", [])
    return next((b["text"] for b in blocks if "text" in b), "")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps({"data": [{"id": MODEL}]}).encode())
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); raw = self.rfile.read(n) if n else b"{}"
        try:
            req = json.loads(raw or b"{}")
            txt = converse_text(req.get("messages", []), req.get("max_tokens", 1500))
            out = {"choices": [{"message": {"role": "assistant", "content": txt}}]}
            code = 200
        except Exception as e:
            out = {"error": str(e)}; code = 500
        b = json.dumps(out).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


if __name__ == "__main__":
    print("bedrock->openai shim on :%d  model=%s" % (PORT, MODEL), flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
