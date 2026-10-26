"""
Release 2 tests for the cloud setup: AI_ENABLED=false.

With the AI switched off the page must still work - cart, checkout and the
orders CRUD - and every AI card must answer straight away with a clear
"turned off" message instead of trying to reach Ollama, RAG, MCP or the
Multi-Agent server.
"""

import importlib

import pytest
import requests

import agent
import main


# FIXTURE: everything AI off, and any network call fails the test
@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(agent, "AI_ENABLED", False)
    monkeypatch.setattr(agent, "RAG_ENABLED", False)
    monkeypatch.setattr(agent, "MCP_ENABLED", False)
    monkeypatch.setattr(agent, "MULTI_AGENT_ENABLED", False)

    def no_network(*args, **kwargs):
        raise AssertionError("AI is off - nothing should be called over the network")

    monkeypatch.setattr(requests, "post", no_network)
    monkeypatch.setattr(requests, "get", no_network)
    monkeypatch.setattr(agent, "ask_llm", no_network)
    monkeypatch.setattr(main, "CUSTOMER_CART", {**main.CUSTOMER_CART, "items": [dict(i) for i in main.DEMO_CART_ITEMS]})
    main.app.testing = True
    return main.app.test_client()


# ENV SWITCH: one variable turns every AI feature off
def test_ai_enabled_false_turns_everything_off(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "false")
    monkeypatch.delenv("RAG_ENABLED", raising=False)
    monkeypatch.delenv("MCP_ENABLED", raising=False)
    monkeypatch.delenv("MULTI_AGENT_ENABLED", raising=False)
    try:
        importlib.reload(agent)
        assert agent.AI_ENABLED is False
        assert agent.RAG_ENABLED is False
        assert agent.MCP_ENABLED is False
        assert agent.MULTI_AGENT_ENABLED is False
    finally:
        monkeypatch.undo()
        importlib.reload(agent)


def test_single_switch_still_works_with_ai_on(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("RAG_ENABLED", "false")
    monkeypatch.delenv("MCP_ENABLED", raising=False)
    try:
        importlib.reload(agent)
        assert agent.AI_ENABLED is True and agent.MCP_ENABLED is True
        assert agent.RAG_ENABLED is False
    finally:
        monkeypatch.undo()
        importlib.reload(agent)


def test_health_shows_ai_is_off(client):
    data = client.get("/api/health").get_json()
    assert data["status"] == "healthy"
    assert data["ai"] == {"ai_enabled": False, "rag": False, "mcp": False, "multi_agent": False}


# AI HELPER: no Ollama call, the facts and safety checks still show
def test_ai_helper_shows_facts_without_calling_ollama(client):
    html = client.post("/api/orders/ai-validate-cart", data={"question": ""}).get_data(as_text=True)
    assert "AI is turned off in this deployment" in html
    assert "Samsung Fridge 500L" in html and "out of stock" in html


def test_ai_helper_json_status_is_disabled(client):
    body = client.post("/api/orders/ai-validate-cart", json={"question": "Weight?"}).get_json()
    assert body["status"] == "disabled" and body["rag_status"] == "disabled"
    assert body["specs_source"] == "database"


# OTHER AI CARDS: clear message, no waiting on timeouts
def test_rag_mcp_and_multi_agent_cards_say_off(client):
    rag = client.post("/api/rag/ask", data={"question": "Returns?"}).get_data(as_text=True)
    mcp = client.post("/api/mcp/order-status", data={"order_id": "1"}).get_data(as_text=True)
    review = client.post("/api/multi-agent/review-cart", data={}).get_data(as_text=True)
    decision = client.post("/api/multi-agent/decision",
                           data={"workflow_id": "wf-1a2b3c4d", "decision": "approve"}).get_data(as_text=True)
    history = client.get("/api/multi-agent/history").get_data(as_text=True)

    assert "RAG is disabled in this deployment" in rag
    assert "MCP is disabled in this deployment" in mcp
    for html in (review, decision, history):
        assert "turned off in this deployment" in html


# CORE APP: cart, checkout and CRUD don't need any AI
def test_cart_and_page_still_work(client):
    assert client.get("/").status_code == 200
    assert "Samsung Fridge 500L" in client.get("/api/cart/view").get_data(as_text=True)
    assert client.get("/api/cart").get_json()["total"] > 0


def test_orders_crud_still_works(client):
    new = {"user_id": 101, "fulfillment_status": "Pending", "items": [
        {"product_id": 514, "product_name": "Air Fryer 20L", "category": "Small Appliances",
         "quantity": 1, "unit_price": 189.0}]}

    created = client.post("/api/orders", json=new)
    assert created.status_code == 201
    order_id = created.get_json()["order_id"]

    assert client.get(f"/api/orders/{order_id}").status_code == 200
    updated = client.put(f"/api/orders/{order_id}", json={"fulfillment_status": "Shipped"})
    assert updated.status_code == 200 and updated.get_json()["fulfillment_status"] == "Shipped"
    assert client.delete(f"/api/orders/{order_id}").status_code == 200
    assert client.get(f"/api/orders/{order_id}").status_code == 404
