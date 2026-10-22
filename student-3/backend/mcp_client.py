"""
Tiny MCP client (plain requests, no extra packages).

Copy this file into your own service to call the shared MCP server:

    from mcp_client import McpClient
    mcp = McpClient(os.getenv("MCP_HOST", "http://localhost:6003"))
    result = mcp.call_tool("get_order_status", {"order_id": 5})
    if result["isError"]: ...                      # tool ran but failed (e.g. not found)
    data = result["structuredContent"]            # the tool's JSON result

(Copied verbatim from ai-services/mcp-server/client.py per that server's README.)
"""

import itertools

import requests


class McpError(Exception):
    """The server rejected the request (unknown tool, bad arguments, ...)."""

    def __init__(self, code, message):
        super().__init__(f"MCP error {code}: {message}")
        self.code = code


class McpClient:
    def __init__(self, host="http://localhost:6003", timeout=30):
        self.url = host.rstrip("/") + "/mcp"
        self.timeout = timeout
        self._ids = itertools.count(1)

    # REQUEST: send one JSON-RPC message and return its result
    def request(self, method, params=None):
        msg = {"jsonrpc": "2.0", "id": next(self._ids), "method": method, "params": params or {}}
        resp = requests.post(self.url, json=msg, timeout=self.timeout,
                             headers={"Accept": "application/json, text/event-stream"})
        body = resp.json()
        if "error" in body:
            raise McpError(body["error"]["code"], body["error"]["message"])
        return body["result"]

    # HANDSHAKE: say hello and learn the server's name + protocol version
    def initialize(self, client_name="omnitech-client"):
        result = self.request("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": client_name, "version": "1.0.0"},
        })
        requests.post(self.url, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, timeout=self.timeout)
        return result

    def list_tools(self):
        return self.request("tools/list")["tools"]

    def call_tool(self, name, arguments=None):
        return self.request("tools/call", {"name": name, "arguments": arguments or {}})
