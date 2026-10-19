"""
Release 1 MCP tests for Student 4: the JSON endpoints the MCP tools call,
the AI helper getting specs through MCP, and the MCP order-lookup card.

No MCP server needed: McpClient is replaced with a fake, and every test uses
its own temporary orders.db, so this file runs in CI.
"""

import copy
import os
import sys

import pytest
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
sys.path.insert(0, os.path.join(HERE, "..", "database"))

import database as db  # noqa: E402
import init_db  # noqa: E402
import agent  # noqa: E402
import main  # noqa: E402
from mcp_client import McpError  # noqa: E402

ORDER_5 = {"order_id": 5, "status": "Processing", "total_price": 1299.5, "created_at": "2026-09-01 10:00:00",
           "item_count": 1, "items": [{"product_name": "Built-in Induction Cooktop 4-Zone", "quantity": 1,
                                       "unit_price": 1299.5}]}


# FAKE MCP CLIENT: records calls, answers like the real server
class FakeMcp:
    calls = []
    mode = "ok"          # ok / tool_error / rejected / offline

    def __init__(self, host, timeout=30):
        self.host = host

    def call_tool(self, name, arguments):
        FakeMcp.calls.append((name, arguments))
        if FakeMcp.mode == "offline":
            raise requests.ConnectionError("refused")
        if FakeMcp.mode == "rejected":
            raise McpError(-32602, "Invalid arguments: 'order_id' must be at least 1")
        if FakeMcp.mode == "tool_error":
            return {"content": [{"type": "text", "text": "Order #999 not found"}], "isError": True}
        if name == "get_order_status":
            return {"content": [{"type": "text", "text": "{}"}], "structuredContent": ORDER_5, "isError": False}
        if name == "get_product_specs":
            specs = db.get_product_specs(arguments["product_ids"])
            return {"structuredContent": {"specs": list(specs.values()), "missing": []}, "isError": False}
        raise AssertionError(f"unexpected tool {name}")


# FIXTURE: temp database, demo cart, MCP on (with the fake), RAG + LLM faked
@pytest.fixture
def setup(tmp_path, monkeypatch):
    db_file = str(tmp_path / "orders.db")
    monkeypatch.setattr(db, "DB_FILE", db_file)
    monkeypatch.setattr(init_db, "DB_FILE", db_file)
    monkeypatch.setattr(db, "_specs_ready", False)
    FakeMcp.calls, FakeMcp.mode = [], "ok"
    monkeypatch.setattr(agent, "McpClient", FakeMcp)
    monkeypatch.setattr(main, "McpClient", FakeMcp)
    monkeypatch.setattr(agent, "MCP_ENABLED", True)
    monkeypatch.setattr(agent, "retrieve_knowledge", lambda query, limit=3: ([], "disabled", None))
    monkeypatch.setattr(agent, "ask_llm", lambda prompt: "The fridge weighs 82 kg.")
    main.CUSTOMER_CART["items"] = copy.deepcopy(main.DEMO_CART_ITEMS)
    main.app.testing = True
    return main.app.test_client()


# --- JSON endpoints used by the MCP tools ---

def test_product_specs_endpoint(setup):
    body = setup.get("/api/products/specs?ids=511,512,9999").get_json()
    assert {s["product_id"] for s in body["specs"]} == {511, 512}
    assert body["missing"] == [9999]
    assert setup.get("/api/products/specs").status_code == 400
    assert setup.get("/api/products/specs?ids=abc").status_code == 400


def test_live_cart_endpoint(setup):
    body = setup.get("/api/cart").get_json()
    assert body["user_id"] == 101
    assert len(body["items"]) == 4
    assert body["total"] == body["subtotal"] + body["delivery_fee"]


# --- AI helper gets specs through MCP ---

def test_agent_loads_specs_via_mcp(setup):
    result = agent.run_cart_agent("How heavy is the fridge?", main.CUSTOMER_CART["items"])
    assert FakeMcp.calls == [("get_product_specs", {"product_ids": [511, 512, 513, 514]})]
    assert result["specs_source"] == "mcp" and result["facts_used"] == 4
    assert "via MCP tool get_product_specs" in result["trace"][0]


def test_agent_falls_back_to_database_when_mcp_offline(setup):
    FakeMcp.mode = "offline"
    result = agent.run_cart_agent("How heavy is the fridge?", main.CUSTOMER_CART["items"])
    assert result["specs_source"] == "database" and result["facts_used"] == 4
    assert "from the database" in result["trace"][0]


def test_agent_skips_mcp_when_disabled(setup, monkeypatch):
    monkeypatch.setattr(agent, "MCP_ENABLED", False)
    result = agent.run_cart_agent("How heavy is the fridge?", main.CUSTOMER_CART["items"])
    assert FakeMcp.calls == [] and result["specs_source"] == "database"


def test_ai_card_shows_specs_came_via_mcp(setup):
    html = setup.post("/api/orders/ai-validate-cart", data={"question": "How heavy?"}).get_data(as_text=True)
    assert "Cart database via MCP (4 products)" in html


# --- MCP order lookup card ---

def test_order_lookup_success(setup):
    html = setup.post("/api/mcp/order-status", data={"order_id": "5"}).get_data(as_text=True)
    assert FakeMcp.calls == [("get_order_status", {"order_id": 5})]
    assert "ai-alert-box success" in html
    assert "get_order_status({&#34;order_id&#34;: 5})" in html      # tool name + inputs shown
    assert "Order #5" in html and "Processing" in html and "Built-in Induction Cooktop 4-Zone" in html
    assert "Raw MCP result" in html


def test_order_lookup_not_found_is_tool_error(setup):
    FakeMcp.mode = "tool_error"
    html = setup.post("/api/mcp/order-status", data={"order_id": "999"}).get_data(as_text=True)
    assert "ai-alert-box warning" in html and "Order #999 not found" in html


def test_order_lookup_rejected_by_server(setup):
    FakeMcp.mode = "rejected"
    html = setup.post("/api/mcp/order-status", data={"order_id": "0"}).get_data(as_text=True)
    assert "ai-alert-box error" in html and "rejected the call" in html and "at least 1" in html


def test_order_lookup_server_offline(setup):
    FakeMcp.mode = "offline"
    html = setup.post("/api/mcp/order-status", data={"order_id": "5"}).get_data(as_text=True)
    assert "MCP server offline" in html


def test_order_lookup_bad_input_and_disabled(setup, monkeypatch):
    html = setup.post("/api/mcp/order-status", data={"order_id": "abc"}).get_data(as_text=True)
    assert "Please enter an order number" in html and FakeMcp.calls == []
    monkeypatch.setattr(agent, "MCP_ENABLED", False)
    html = setup.post("/api/mcp/order-status", data={"order_id": "5"}).get_data(as_text=True)
    assert "MCP is disabled" in html and FakeMcp.calls == []


def test_page_has_mcp_card(setup):
    html = setup.get("/").get_data(as_text=True)
    assert 'hx-post="/api/mcp/order-status"' in html
