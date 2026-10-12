"""
Tests for Student 5's tools on the shared MCP server.

Student services is not needed: the Student 5 REST API is replaced with
a fake (monkeypatched requests.get), using the same approach as the
other shared MCP tool tests.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import registry  # noqa: E402
import server  # noqa: E402  (importing server loads every tools/*.py module)

PRODUCT_1 = {
    "product_id": 1,
    "product_name": "Meridian Pro 16",
    "product_category": "Laptop",
    "product_price": 2499.99,
    "product_description": "High-performance laptop for professional use.",
    "product_warranty_years": 2,
}

class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        
    def json(self):
        return self._body

def fake_get(url, params=None, timeout=None):
    fake_get.calls.append((url, params))
    if url.endswith("/api/products/1"):
        return FakeResponse(200, PRODUCT_1)
    return FakeResponse(404, {"error": "not found"})

@pytest.fixture
def client(monkeypatch):
    fake_get.calls = []
    monkeypatch.setattr(registry.requests, "get", fake_get)
    server.app.testing = True
    return server.app.test_client()

def rpc(client, method, params=None, msg_id=1):
    body = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if msg_id is not None:
        body["id"] = msg_id
    return client.post("/mcp", json=body)

def call(client, name, arguments):
    return rpc(client, "tools/call", {"name": name,"arguments": arguments}).get_json()

def test_health_lists_get_warranty_product(client):
    body = client.get("/health").get_json()
    assert "get_warranty_product" in body["tools"]
    assert body["owners"]["get_warranty_product"] == "student5"

def test_get_warranty_product(client):
    res = call(client, "get_warranty_product", {"product_id": 1})["result"]
    assert res["isError"] is False
    product = res["structuredContent"]
    assert product["product_id"] == 1
    assert product["product_name"] == "Meridian Pro 16"
    assert product["product_category"] == "Laptop"
    assert product["product_price"] == 2499.99
    assert product["product_description"] == "High-performance laptop for professional use."
    assert product["product_warranty_years"] == 2
    assert fake_get.calls[0][0] == "http://localhost:5005/api/products/1"

def test_get_warranty_product_not_found(client):
    res = call(client, "get_warranty_product", {"product_id": 999})["result"]
    assert res["isError"] is True
    assert res["content"][0]["text"] == "Product #999 not found"

def test_get_warranty_product_rejects_bad_input(client):
    res = call(client, "get_warranty_product", {"product_id": "1"})
    assert res["error"]["code"] == -32602