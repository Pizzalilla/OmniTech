"""
Tests for Student 3's tools on the shared MCP server. No student services are
needed: Student 3's REST API is replaced with a fake (monkeypatched
requests.get), same approach as tests/test_server.py uses for Student 4.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import registry  # noqa: E402
import server  # noqa: E402  (importing server loads every tools/*.py module)

RECOMMENDATIONS = [
    {"id": 1, "session_id": 1, "product_ids": ["LAP-001"],
     "products": [{"id": "LAP-001", "name": "Meridian Pro 16"}],
     "summary": "Workstation laptop for 4K editing.",
     "tags": ["video-editing"], "created_at": "2026-09-01 10:00:00"},
]


class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


def fake_get(url, params=None, timeout=None):
    fake_get.calls.append((url, params))
    if url.endswith("/api/sessions/1/recommendations"):
        return FakeResponse(200, RECOMMENDATIONS)
    if url.endswith("/api/sessions/2/recommendations"):
        return FakeResponse(200, [])
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
    return rpc(client, "tools/call", {"name": name, "arguments": arguments}).get_json()


def test_health_lists_get_saved_recommendations(client):
    body = client.get("/health").get_json()
    assert "get_saved_recommendations" in body["tools"]
    assert body["owners"]["get_saved_recommendations"] == "student3"


def test_get_saved_recommendations(client):
    res = call(client, "get_saved_recommendations", {"session_id": 1})["result"]
    assert res["isError"] is False
    assert res["structuredContent"]["session_id"] == 1
    assert res["structuredContent"]["recommendations"][0]["summary"] == \
        "Workstation laptop for 4K editing."
    assert fake_get.calls[0][0] == "http://localhost:5003/api/sessions/1/recommendations"


def test_get_saved_recommendations_empty_session_is_not_an_error(client):
    res = call(client, "get_saved_recommendations", {"session_id": 2})["result"]
    assert res["isError"] is False
    assert res["structuredContent"]["recommendations"] == []


def test_get_saved_recommendations_session_not_found(client):
    res = call(client, "get_saved_recommendations", {"session_id": 999})["result"]
    assert res["isError"] is True
    assert res["content"][0]["text"] == "Session #999 not found"


def test_get_saved_recommendations_rejects_bad_input(client):
    res = call(client, "get_saved_recommendations", {"session_id": "1"})
    assert res["error"]["code"] == -32602
