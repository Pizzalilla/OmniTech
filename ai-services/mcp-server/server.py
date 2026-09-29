"""
Shared MCP (Model Context Protocol) server for the OmniTech Release 1 project.

Runs on the PC (not in Docker), like Ollama and the RAG server. It speaks MCP
over HTTP: JSON-RPC 2.0 messages POSTed to /mcp, answered with plain JSON
(the "Streamable HTTP" transport, JSON-response mode, no sessions).

Supported MCP methods:
    initialize                 handshake - server name, version, capabilities
    notifications/initialized  client says it's ready (no reply)
    ping                       liveness
    tools/list                 every registered tool with its input schema
    tools/call                 run one tool: {"name": ..., "arguments": {...}}

Other endpoints:
    GET /health   status + registered tool names (for quick checks)

Run directly (not via Docker):
    python server.py        -> http://localhost:6003/mcp
"""

import importlib
import json
import logging
import os
import pkgutil
from urllib.parse import urlparse

from flask import Flask, jsonify, request

import registry

MCP_PORT = int(os.getenv("MCP_PORT", "6003"))
SERVER_INFO = {"name": "omnitech-mcp-server", "version": "1.0.0"}
PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]

log = logging.getLogger("mcp-server")
if not log.handlers:
    log.setLevel(logging.INFO)
    log.addHandler(logging.StreamHandler())
for _h in log.handlers:
    _h.setFormatter(logging.Formatter("%(asctime)s  mcp  %(message)s"))

app = Flask(__name__)


class UnknownTool(Exception):
    """tools/call named a tool that isn't registered."""


# LOAD TOOLS: import every tools/*.py (files starting with _ are skipped)
def load_tools():
    import tools
    for mod in pkgutil.iter_modules(tools.__path__):
        if not mod.name.startswith("_"):
            importlib.import_module(f"tools.{mod.name}")


load_tools()


# JSON-RPC HELPERS
def rpc_result(msg_id, result):
    return jsonify({"jsonrpc": "2.0", "id": msg_id, "result": result})


def rpc_error(msg_id, code, message):
    return jsonify({"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}})


def text_result(data, is_error=False):
    text = data if isinstance(data, str) else json.dumps(data)
    result = {"content": [{"type": "text", "text": text}], "isError": is_error}
    if not is_error:
        result["structuredContent"] = data if isinstance(data, dict) else {"result": data}
    return result


# METHODS
def handle_initialize(params):
    asked = params.get("protocolVersion")
    return {
        "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": SERVER_INFO,
        "instructions": "OmniTech marketplace tools. All tools are read-only.",
    }


def handle_tools_call(params):
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if name not in registry.TOOLS:
        raise UnknownTool(f"Unknown tool: {name}")
    try:
        data = registry.call_tool(name, arguments)
        log.info("CALL   %s %s -> ok", name, arguments)
        return text_result(data)
    except registry.ToolError as exc:
        log.info("CALL   %s %s -> tool error: %s", name, arguments, exc)
        return text_result(str(exc), is_error=True)


# SECURITY: only accept browser requests from this machine (stops DNS-rebinding)
def origin_allowed():
    origin = request.headers.get("Origin")
    if not origin:
        return True
    # compare the exact hostname so "http://localhost.evil.com" is not let through
    return urlparse(origin).hostname in ("localhost", "127.0.0.1", "host.docker.internal")


@app.route("/mcp", methods=["POST"])
def mcp():
    if not origin_allowed():
        return jsonify({"error": "origin not allowed"}), 403

    try:
        msg = json.loads(request.get_data(as_text=True) or "")
    except ValueError:
        return rpc_error(None, -32700, "Parse error: body is not valid JSON"), 400
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return rpc_error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid JSON-RPC request"), 400

    # RESPONSES: a client answering us (result/error, no method) -> accepted, no reply body
    if "method" not in msg and ("result" in msg or "error" in msg):
        return "", 202
    if "method" not in msg:
        return rpc_error(msg.get("id"), -32600, "Invalid JSON-RPC request"), 400

    method, params, msg_id = msg["method"], msg.get("params") or {}, msg.get("id")
    if not isinstance(params, dict):
        return rpc_error(msg_id, -32602, "Invalid params: params must be an object"), 400

    # NOTIFICATIONS: no id -> no reply body
    if msg_id is None:
        log.info("NOTIFY %s", method)
        return "", 202

    try:
        if method == "initialize":
            log.info("INIT   client=%s", (params.get("clientInfo") or {}).get("name", "?"))
            return rpc_result(msg_id, handle_initialize(params))
        if method == "ping":
            return rpc_result(msg_id, {})
        if method == "tools/list":
            log.info("LIST   %d tool(s)", len(registry.TOOLS))
            return rpc_result(msg_id, {"tools": registry.list_tools()})
        if method == "tools/call":
            return rpc_result(msg_id, handle_tools_call(params))
        return rpc_error(msg_id, -32601, f"Method not found: {method}")
    except UnknownTool as exc:
        return rpc_error(msg_id, -32602, str(exc))
    except registry.InvalidArguments as exc:
        log.info("CALL   %s rejected: %s", params.get("name"), exc)
        return rpc_error(msg_id, -32602, f"Invalid arguments: {exc}")
    except Exception as exc:  # a bug in a tool must not crash the server
        log.exception("CALL   %s crashed", params.get("name"))
        return rpc_result(msg_id, text_result(f"Tool failed: {type(exc).__name__}", is_error=True))


@app.route("/mcp", methods=["GET", "DELETE"])
def mcp_other():
    # No server-to-client stream and no sessions in this server
    return jsonify({"error": "Use POST /mcp with a JSON-RPC message"}), 405


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "tools": sorted(registry.TOOLS),
        "owners": {name: t["owner"] for name, t in registry.TOOLS.items()},
        "examples": {name: t["example"] for name, t in registry.TOOLS.items()},
        "services": registry.SERVICES,
    })


if __name__ == "__main__":
    log.info("MCP server starting on port %d with %d tool(s): %s",
             MCP_PORT, len(registry.TOOLS), ", ".join(sorted(registry.TOOLS)))
    app.run(host="0.0.0.0", port=MCP_PORT, threaded=True)
