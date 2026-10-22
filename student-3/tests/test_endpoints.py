"""Release 2 post-commit CI/CD endpoint tests: the two endpoint functions
Student 3 tests in .github/workflows/student-3.yml.

1. create_session()  POST /api/sessions  - start a consultation (CRUD entry point)
2. chat()            POST /api/chat      - one turn of the agentic consultation loop

Ollama, RAG, MCP and the Multi-Agent server are never called: the model is
faked or forced offline, the same way the feature runs in CI and in the cloud
(where AI is disabled by default).
"""

import json

import pytest
import requests

import agent
import catalog


def _messages(client, session_id):
    return json.loads(client.get(f"/api/sessions/{session_id}/messages").data)


@pytest.fixture
def ollama_offline(monkeypatch):
    def _down(prompt):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(agent, "act", _down)


# ── Endpoint 1: POST /api/sessions ──────────────────────────────────────────

def test_create_session_returns_201_with_fields(client):
    rv = client.post("/api/sessions", json={"title": "Test", "user_id": "u-42"})
    assert rv.status_code == 201
    data = json.loads(rv.data)
    assert data["title"] == "Test"
    assert data["user_id"] == "u-42"
    assert isinstance(data["id"], int)
    assert data["created_at"]


def test_create_session_is_persisted(client):
    new_id = json.loads(client.post("/api/sessions", json={"title": "Desk setup"}).data)["id"]
    rv = client.get(f"/api/sessions/{new_id}")
    assert rv.status_code == 200
    assert json.loads(rv.data)["session"]["title"] == "Desk setup"
    assert new_id in [s["id"] for s in json.loads(client.get("/api/sessions").data)]


def test_create_session_defaults_without_body(client):
    rv = client.post("/api/sessions")
    assert rv.status_code == 201
    data = json.loads(rv.data)
    assert data["title"] == "New Consultation"
    assert data["user_id"] == "guest"


def test_create_session_blank_values_fall_back_to_defaults(client):
    data = json.loads(client.post("/api/sessions", json={"title": "   ", "user_id": " "}).data)
    assert data["title"] == "New Consultation"
    assert data["user_id"] == "guest"


def test_create_session_title_is_stored_as_text_not_sql(client):
    title = "x'); DROP TABLE ConsultationSessions; --"
    data = json.loads(client.post("/api/sessions", json={"title": title}).data)
    assert data["title"] == title
    assert client.get("/api/sessions").status_code == 200


# ── Endpoint 2: POST /api/chat ──────────────────────────────────────────────

def test_chat_requires_fields(client):
    assert client.post("/api/chat", json={}).status_code == 400
    assert client.post("/api/chat", json={"session_id": 1, "message": "   "}).status_code == 400


def test_chat_session_not_found(client):
    rv = client.post("/api/chat", json={"session_id": 9999, "message": "hi"})
    assert rv.status_code == 404
    assert json.loads(rv.data)["error"] == "Session not found"


def test_chat_valid_model_answer_saves_recommendation(client, fake_ollama):
    rv = client.post("/api/chat", json={"session_id": 3, "message": "laptop for 4K editing"})
    assert rv.status_code == 200
    body = json.loads(rv.data)
    assert body["recommended_product_ids"] == ["LAP-001"]
    assert body["meta"]["used_fallback"] is False
    assert body["saved_recommendation"]["product_ids"] == ["LAP-001"]


def test_chat_persists_both_turns_when_ollama_is_offline(client, ollama_offline):
    """The cloud deployment has no Ollama: the catalog fallback must still reply
    and both turns must be saved."""
    before = len(_messages(client, 2))
    rv = client.post("/api/chat", json={"session_id": 2, "message": "cheap phone for my mum"})
    assert rv.status_code == 200
    body = json.loads(rv.data)
    assert body["reply"]
    assert body["meta"]["used_fallback"] is True
    assert set(body["recommended_product_ids"]) <= catalog.VALID_IDS
    after = _messages(client, 2)
    assert len(after) == before + 2
    assert [m["sender"] for m in after[-2:]] == ["user", "ai"]


def test_chat_rejects_hallucinated_product_ids(client, monkeypatch):
    """A model answer citing a product that does not exist is never saved."""
    monkeypatch.setattr(agent, "act", lambda prompt: json.dumps({
        "reply": "Buy the Imaginary X (FAKE-999).",
        "recommended_product_ids": ["FAKE-999"],
        "summary": "Not a real product.",
    }))
    body = json.loads(client.post("/api/chat", json={"session_id": 3, "message": "laptop"}).data)
    assert "FAKE-999" not in body["recommended_product_ids"]
    assert set(body["recommended_product_ids"]) <= catalog.VALID_IDS


def test_chat_htmx_returns_html_fragment(client, fake_ollama):
    rv = client.post("/api/chat", data={"session_id": "3", "message": "laptop for editing"},
                     headers={"HX-Request": "true"})
    assert rv.status_code == 200
    assert b"msg--ai" in rv.data
    assert b"hx-swap-oob" in rv.data
