"""
Tests for the shared MCP server. No student services are needed: the
Student 4 REST API is replaced with a fake (monkeypatched requests.get).
"""

import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import registry  # noqa: E402
import server  # noqa: E402
from client import McpClient, McpError  # noqa: E402

ORDER_5 = {
    "order_id": 5, "user_id": 105, "total_price": 1299.5, "fulfillment_status": "Processing",
    "created_at": "2026-09-01 10:00:00",
    "line_items": [{"product_name": "Built-in Induction Cooktop 4-Zone", "quantity": 1, "unit_price": 1299.5}],
}
CART = {"user_id": 101, "fulfillment": "delivery", "items": [{"product_id": 511, "quantity": 1}], "total": 1514.0}
SPECS = {"specs": [{"product_id": 511, "product_name": "Samsung Fridge 500L", "power_w": 180}], "missing": [512]}


class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


# FAKE STUDENT 4 API: answers the GET calls the tools make
def fake_get(url, params=None, timeout=None):
    fake_get.calls.append((url, params))
    if url.endswith("/api/orders/5"):
        return FakeResponse(200, ORDER_5)
    if url.endswith("/api/cart"):
        return FakeResponse(200, CART)
    if url.endswith("/api/products/specs"):
        return FakeResponse(200, SPECS)
    return FakeResponse(404, {"error": "not found"})


@pytest.fixture
def client(monkeypatch):
    fake_get.calls = []
    monkeypatch.setattr(registry.requests, "get", fake_get)

    # BOUNDARY: tools must never write - any non-GET call fails the test
    def _no_writes(*a, **k):
        raise AssertionError("tools must only use GET")
    for verb in ("post", "put", "patch", "delete"):
        monkeypatch.setattr(registry.requests, verb, _no_writes)

    server.app.testing = True
    return server.app.test_client()


def rpc(client, method, params=None, msg_id=1):
    body = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if msg_id is not None:
        body["id"] = msg_id
    return client.post("/mcp", json=body)


def call(client, name, arguments):
    return rpc(client, "tools/call", {"name": name, "arguments": arguments}).get_json()


# --- handshake + discovery ---

def test_health_lists_student4_tools(client):
    body = client.get("/health").get_json()
    assert body["status"] == "ok"
    assert {"get_order_status", "get_cart", "get_product_specs"} <= set(body["tools"])
    assert body["owners"]["get_order_status"] == "student4"
    assert "get_something" not in body["tools"]          # _template.py is not loaded


def test_initialize_returns_server_info_and_protocol(client):
    res = rpc(client, "initialize", {"protocolVersion": "2025-06-18", "clientInfo": {"name": "t"}}).get_json()
    assert res["result"]["serverInfo"]["name"] == "omnitech-mcp-server"
    assert res["result"]["protocolVersion"] == "2025-06-18"
    assert res["result"]["capabilities"]["tools"] == {"listChanged": False}

    older = rpc(client, "initialize", {"protocolVersion": "2024-11-05"}).get_json()
    assert older["result"]["protocolVersion"] == "2024-11-05"
    unknown = rpc(client, "initialize", {"protocolVersion": "1999-01-01"}).get_json()
    assert unknown["result"]["protocolVersion"] == "2025-06-18"


def test_notification_gets_202_and_no_body(client):
    res = rpc(client, "notifications/initialized", msg_id=None)
    assert res.status_code == 202 and res.get_data() == b""


def test_ping(client):
    assert rpc(client, "ping").get_json()["result"] == {}


def test_tools_list_has_schemas_and_read_only_hint(client):
    tools = {t["name"]: t for t in rpc(client, "tools/list").get_json()["result"]["tools"]}
    t = tools["get_order_status"]
    assert t["description"]
    assert t["inputSchema"]["properties"]["order_id"]["type"] == "integer"
    assert t["inputSchema"]["required"] == ["order_id"]
    assert t["inputSchema"]["additionalProperties"] is False
    assert all(tool["annotations"]["readOnlyHint"] for tool in tools.values())
    assert "handler" not in t and "example" not in t


# --- tools/call ---

def test_get_order_status(client):
    res = call(client, "get_order_status", {"order_id": 5})["result"]
    assert res["isError"] is False
    assert res["structuredContent"]["status"] == "Processing"
    assert res["structuredContent"]["item_count"] == 1
    assert '"status": "Processing"' in res["content"][0]["text"]
    assert fake_get.calls[0][0] == "http://localhost:5004/api/orders/5"


def test_get_order_status_not_found_is_tool_error(client):
    res = call(client, "get_order_status", {"order_id": 999})["result"]
    assert res["isError"] is True
    assert res["content"][0]["text"] == "Order #999 not found"


def test_get_cart_and_specs(client):
    assert call(client, "get_cart", {})["result"]["structuredContent"]["total"] == 1514.0
    res = call(client, "get_product_specs", {"product_ids": [511, 512]})["result"]
    assert res["structuredContent"]["missing"] == [512]
    assert fake_get.calls[-1][1] == {"ids": "511,512"}


def test_service_down_is_tool_error(client, monkeypatch):
    def _down(*a, **k):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(registry.requests, "get", _down)
    res = call(client, "get_order_status", {"order_id": 5})["result"]
    assert res["isError"] is True and "not reachable" in res["content"][0]["text"]


# --- boundaries: bad calls are rejected before the tool runs ---

@pytest.mark.parametrize("name, arguments, message", [
    ("delete_everything", {}, "Unknown tool"),
    ("get_order_status", {}, "missing required"),
    ("get_order_status", {"order_id": "5"}, "must be integer"),
    ("get_order_status", {"order_id": True}, "must be integer"),
    ("get_order_status", {"order_id": 0}, "at least 1"),
    ("get_order_status", {"order_id": 5, "drop_table": True}, "unknown argument"),
    ("get_product_specs", {"product_ids": []}, "at least 1 item"),
    ("get_product_specs", {"product_ids": [511, "x"]}, "must be integer"),
    ("get_product_specs", {"product_ids": list(range(1, 30))}, "at most 20"),
])
def test_bad_calls_are_rejected(client, name, arguments, message):
    res = call(client, name, arguments)
    assert res["error"]["code"] == -32602
    assert message in res["error"]["message"]
    assert fake_get.calls == []          # the tool never ran


def test_service_get_only_knows_student_services():
    with pytest.raises(registry.ToolError):
        registry.service_get("evil-service", "/anything")


def test_crashing_tool_does_not_crash_server(client):
    @registry.tool(name="_broken_tool", description="test only")
    def _broken():
        raise KeyError("oops")
    try:
        res = call(client, "_broken_tool", {})["result"]
        assert res["isError"] is True and "Tool failed: KeyError" in res["content"][0]["text"]
    finally:
        registry.TOOLS.pop("_broken_tool")


# --- JSON-RPC errors ---

def test_protocol_errors(client):
    bad_json = client.post("/mcp", data="{not json", content_type="application/json")
    assert bad_json.status_code == 400 and bad_json.get_json()["error"]["code"] == -32700

    not_rpc = client.post("/mcp", json={"hello": "world"})
    assert not_rpc.get_json()["error"]["code"] == -32600

    assert rpc(client, "resources/list").get_json()["error"]["code"] == -32601
    assert client.get("/mcp").status_code == 405


def test_foreign_browser_origin_is_blocked(client):
    body = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    assert client.post("/mcp", json=body, headers={"Origin": "http://evil.example"}).status_code == 403
    assert client.post("/mcp", json=body, headers={"Origin": "http://localhost:5004"}).status_code == 200


# --- the client helper, routed into the test server ---

def test_mcp_client_round_trip(client, monkeypatch):
    import client as client_module

    def _post(url, json=None, timeout=None, headers=None):
        res = client.post("/mcp", json=json)
        return FakeResponse(res.status_code, res.get_json())
    monkeypatch.setattr(client_module.requests, "post", _post)

    mcp = McpClient("http://localhost:6003")
    assert mcp.initialize()["serverInfo"]["name"] == "omnitech-mcp-server"
    assert "get_cart" in [t["name"] for t in mcp.list_tools()]
    assert mcp.call_tool("get_order_status", {"order_id": 5})["structuredContent"]["order_id"] == 5
    with pytest.raises(McpError) as err:
        mcp.call_tool("get_order_status", {})
    assert err.value.code == -32602
