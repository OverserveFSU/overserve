# OpenAI-compatible -> litellm(Bedrock sonnet-5) shim WITH Anthropic/Bedrock prompt caching.
# Same contract as bedrock_shim.py (POST /v1/chat/completions on :SHIM_PORT, forces SHIM_MODEL),
# but injects cache_control breakpoints so the static (system + tools) prefix and the growing
# conversation prefix are served from Bedrock's prompt cache across the multi-turn agent loop.
#
# Cost-control for the OverServe sonnet-5 victim-generalization test. Verify caching is live via
# the usage fields cache_creation_input_tokens / cache_read_input_tokens in the response.
import json, os, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import litellm
litellm.drop_params = True  # sonnet-5 rejects temperature=0/top_p etc.; drop unsupported sampling params

MODEL = os.environ.get("SHIM_MODEL", "bedrock/us.anthropic.claude-sonnet-5")
PORT = int(os.environ.get("SHIM_PORT", "8300"))
CACHE = os.environ.get("SHIM_CACHE", "1") == "1"

_CC = {"type": "ephemeral"}


def _as_blocks(content):
    """Normalize OpenAI message content (str or list) to a list of content blocks."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return list(content)
    return [{"type": "text", "text": str(content)}]


def _mark_last_block(blocks):
    """Attach cache_control to the last text-bearing block in-place; return blocks."""
    for b in reversed(blocks):
        if isinstance(b, dict) and b.get("type") in ("text", None):
            b["cache_control"] = _CC
            return blocks
    if blocks and isinstance(blocks[-1], dict):
        blocks[-1]["cache_control"] = _CC
    return blocks


def _inject_cache(kw):
    """Add up to-4 Anthropic/Bedrock cache breakpoints:
      1) last tool  -> caches the (static) tool-definition + system prefix,
      2) system msg -> cached text block,
      3) last message -> caches the growing conversation prefix each turn.
    Mutates kw in place."""
    # (1) tools: cache the definition block (static across all turns)
    tools = kw.get("tools")
    if isinstance(tools, list) and tools:
        last = tools[-1]
        if isinstance(last, dict):
            last["cache_control"] = _CC

    msgs = kw.get("messages") or []
    # (2) system message -> cached text block
    for m in msgs:
        if isinstance(m, dict) and m.get("role") == "system":
            m["content"] = _mark_last_block(_as_blocks(m.get("content", "")))
            break
    # (3) last message -> cache the conversation prefix up to here
    if msgs:
        last = msgs[-1]
        if isinstance(last, dict) and last.get("role") in ("user", "assistant", "tool"):
            # tool-role results translate to toolResult blocks; marking the text block is safe
            last["content"] = _mark_last_block(_as_blocks(last.get("content", "")))
    return kw


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
            self._send(200, {"status": "ok", "cache": CACHE})

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
        if CACHE:
            try:
                _inject_cache(kw)
            except Exception:
                traceback.print_exc()  # never fail a request because of caching
        try:
            r = litellm.completion(**kw)
            out = r.model_dump() if hasattr(r, "model_dump") else json.loads(r.json())
            try:
                u = out.get("usage") or {}
                logf = os.environ.get("SHIM_USAGE_LOG")
                if logf:
                    with open(logf, "a") as lf:
                        lf.write(json.dumps({
                            "in": u.get("prompt_tokens"),
                            "out": u.get("completion_tokens"),
                            "cw": u.get("cache_creation_input_tokens"),
                            "cr": u.get("cache_read_input_tokens"),
                        }) + "\n")
            except Exception:
                pass
            self._send(200, out)
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"error": {"message": str(e)[:500], "type": "shim_error"}})


if __name__ == "__main__":
    print("bedrock cache shim: %s on 0.0.0.0:%d (cache=%s)" % (MODEL, PORT, CACHE), flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
