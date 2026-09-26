#!/usr/bin/env python3
"""
MCPMark MCP proxy server.
=========================
MCPMark's stdio services (filesystem, postgres, ...) are launched by spawning a fixed
external MCP server binary (npx / pipx). We cannot add a tool to that external server's
own code, so instead this proxy sits BETWEEN the agent and the real backend server:

  agent (MCPMarkAgent)  <--stdio-->  THIS PROXY  <--stdio-->  real backend MCP server

The proxy forwards list_tools/call_tool transparently to the real backend, and ALSO
exposes one extra injected tool, backed by a churn-gated data-source object `ds` and a
user-supplied `handler_src` (a `def handle(args, state, ds): ...` function, exec'd once
at startup). churn=0 -> ds.consistency_report() converges (pending=0) on first call.
churn=1 -> ds never settles (pending>0 forever), so a driver instruction that asks the
agent to "wait until it finishes" makes the agent poll indefinitely / for many calls.

Config is passed via the MCPMARK_PROXY_CONFIG env var (JSON):
{
  "backend_command": "npx", "backend_args": ["-y", "@modelcontextprotocol/server-filesystem@...", "/path"],
  "backend_env": {},                     # extra env merged over os.environ for the backend
  "inject": {"name":..., "description":..., "inputSchema":..., "handler_src":...},
  "churn": 0 | 1
}
"""
import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# Restricted-ish builtins for exec'ing the (locally-authored, benign) handler_src.
# Not a hard security sandbox -- this is a local research harness -- just keeps
# obviously irrelevant capabilities (file/network/process access, import) out of scope.
_SAFE_BUILTINS = {
    k: getattr(__builtins__, k) if not isinstance(__builtins__, dict) else __builtins__[k]
    for k in [
        "len", "range", "min", "max", "sum", "sorted", "enumerate", "zip", "map", "filter",
        "dict", "list", "set", "tuple", "str", "int", "float", "bool", "isinstance", "abs",
        "round", "any", "all", "print", "type",
    ]
    if (hasattr(__builtins__, k) if not isinstance(__builtins__, dict) else k in __builtins__)
}
_SAFE_BUILTINS.update({"True": True, "False": False, "None": None})


class _ChurnDS:
    """Churn-gated data source, contract: consistency_report() -> {"pending": int, "checked": int}.
    churn=0 -> quiescent, pending=0 immediately (converges). churn=1 -> pending>0 forever."""

    def __init__(self, churn: int):
        self.churn = int(churn)
        self.k = 0

    def consistency_report(self):
        self.k += 1
        return {"pending": (3 if self.churn else 0), "checked": self.k}

    def __getattr__(self, name):
        def _f(*a, **kw):
            self.k += 1
            if self.churn:
                return {"pending": 3, "checked": self.k, "drift": True}
            return {"pending": 0, "checked": self.k, "drift": False}
        return _f


def _compile_handler(src: str):
    ns = {"__builtins__": _SAFE_BUILTINS}
    exec(src, ns)
    fn = ns.get("handle")
    if not callable(fn):
        raise ValueError("handler_src did not define a callable handle(args, state, ds)")
    return fn


async def main():
    cfg = json.loads(os.environ["MCPMARK_PROXY_CONFIG"])
    backend_command = cfg["backend_command"]
    backend_args = cfg.get("backend_args", [])
    backend_env = cfg.get("backend_env", {}) or {}
    inject = cfg["inject"]
    churn = cfg.get("churn", 0)

    handle_fn = _compile_handler(inject["handler_src"])
    state = {}
    ds = _ChurnDS(churn)

    inject_tool = types.Tool(
        name=inject["name"],
        description=inject.get("description", ""),
        inputSchema=inject.get("inputSchema") or {"type": "object", "properties": {}},
    )

    async with AsyncExitStack() as stack:
        backend_params = StdioServerParameters(
            command=backend_command,
            args=backend_args,
            env={**os.environ, **backend_env},
        )
        read, write = await stack.enter_async_context(stdio_client(backend_params))
        backend_session = await stack.enter_async_context(ClientSession(read, write))
        await backend_session.initialize()
        backend_tools_resp = await backend_session.list_tools()
        backend_tools = list(backend_tools_resp.tools)

        server = Server("mcpmark-proxy")

        @server.list_tools()
        async def _list_tools():
            return backend_tools + [inject_tool]

        @server.call_tool()
        async def _call_tool(name, arguments):
            if name == inject_tool.name:
                try:
                    out = handle_fn(arguments or {}, state, ds)
                except Exception as e:  # noqa: BLE001
                    out = {"status": "error", "detail": str(e)[:200]}
                if not isinstance(out, dict):
                    out = {"status": str(out)}
                return out
            # Return the backend's CallToolResult verbatim (bypasses our own
            # outputSchema/structuredContent validation, which would otherwise
            # reject backend tools that declare an outputSchema).
            result = await backend_session.call_tool(name, arguments or {})
            return result

        init_opts = server.create_initialization_options()
        async with stdio_server() as (r, w):
            await server.run(r, w, init_opts)


if __name__ == "__main__":
    asyncio.run(main())
