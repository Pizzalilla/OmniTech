import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "database"))

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "bootstrap.db")

import agent  # noqa: E402
import database  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture
def client(tmp_path):
    # Fresh, isolated database per test so destructive cases cannot bleed.
    database.DB_PATH = str(tmp_path / "test.db")
    database.init_db()
    database.seed_db()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def fake_ollama(monkeypatch):
    """Force agent.act to return a valid, catalog-consistent JSON answer."""
    def _act(prompt):
        return json.dumps({
            "reply": "The Meridian Pro 16 (LAP-001) is the best fit for 4K editing.",
            "recommended_product_ids": ["LAP-001"],
            "summary": "Workstation laptop for heavy 4K timelines.",
        })
    monkeypatch.setattr(agent, "act", _act)


# ── Pages ────────────────────────────────────────────────────────────────────

def test_index_page(client):
    rv = client.get("/")
    assert rv.status_code == 200
    assert b"AI Product Consultant" in rv.data


def test_dashboard_page(client):
    rv = client.get("/dashboard")
    assert rv.status_code == 200
    assert b"Past consultations" in rv.data
    assert b"Saved product recommendations" in rv.data


# ── Sessions CRUD ───────────────────────────────────────────────────────────

def test_list_sessions(client):
    rv = client.get("/api/sessions")
    assert rv.status_code == 200
    assert len(json.loads(rv.data)) >= 10


def test_list_sessions_filtered_by_user(client):
    rv = client.get("/api/sessions?user_id=u-1001")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data and all(s["user_id"] == "u-1001" for s in data)


def test_create_session_with_user(client):
    rv = client.post("/api/sessions", json={"title": "Test", "user_id": "u-42"})
    assert rv.status_code == 201
    data = json.loads(rv.data)
    assert data["title"] == "Test"
    assert data["user_id"] == "u-42"


def test_get_session_bundle(client):
    rv = client.get("/api/sessions/1")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert set(data) == {"session", "messages", "recommendations"}
    assert data["session"]["id"] == 1


def test_get_session_not_found(client):
    assert client.get("/api/sessions/9999").status_code == 404


def test_update_session_title(client):
    rv = client.put("/api/sessions/1", json={"title": "Renamed"})
    assert rv.status_code == 200
    assert json.loads(rv.data)["title"] == "Renamed"


def test_update_session_requires_title(client):
    assert client.put("/api/sessions/1", json={}).status_code == 400


def test_delete_session(client):
    new_id = json.loads(client.post("/api/sessions", json={"title": "x"}).data)["id"]
    assert client.delete(f"/api/sessions/{new_id}").status_code == 200
    assert client.get(f"/api/sessions/{new_id}").status_code == 404


def test_delete_session_cascades(client):
    client.delete("/api/sessions/1")
    assert client.get("/api/sessions/1/messages").status_code == 404


# ── ChatLogs CRUD ───────────────────────────────────────────────────────────

def test_list_messages(client):
    rv = client.get("/api/sessions/1/messages")
    assert rv.status_code == 200
    assert len(json.loads(rv.data)) >= 2


def test_create_message(client):
    rv = client.post("/api/sessions/1/messages",
                     json={"sender": "user", "message_text": "hello"})
    assert rv.status_code == 201
    assert json.loads(rv.data)["sender"] == "user"


def test_create_message_rejects_bad_sender(client):
    rv = client.post("/api/sessions/1/messages",
                     json={"sender": "robot", "message_text": "hi"})
    assert rv.status_code == 400


def test_clear_chat_history(client):
    assert client.delete("/api/sessions/1/messages").status_code == 200
    assert json.loads(client.get("/api/sessions/1/messages").data) == []


def test_delete_single_message(client):
    mid = json.loads(client.get("/api/sessions/1/messages").data)[0]["id"]
    assert client.delete(f"/api/messages/{mid}").status_code == 200


# ── SavedRecommendations CRUD ──────────────────────────────────────────────

def test_list_recommendations(client):
    rv = client.get("/api/sessions/1/recommendations")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data and "products" in data[0]


def test_create_recommendation(client):
    rv = client.post("/api/recommendations", json={
        "session_id": 1,
        "product_ids": ["LAP-001", "MON-001"],
        "summary": "editing bundle",
        "tags": ["work"],
    })
    assert rv.status_code == 201
    data = json.loads(rv.data)
    assert data["product_ids"] == ["LAP-001", "MON-001"]
    assert data["tags"] == ["work"]


def test_create_recommendation_rejects_unknown_products(client):
    rv = client.post("/api/recommendations",
                     json={"session_id": 1, "product_ids": ["NOPE-999"]})
    assert rv.status_code == 400


def test_update_recommendation_tags(client):
    rv = client.put("/api/recommendations/1", json={"tags": "new,updated"})
    assert rv.status_code == 200
    assert "new" in json.loads(rv.data)["tags"]


def test_add_single_tag(client):
    rv = client.post("/api/recommendations/1/tags", data={"tag": "Great Value"})
    assert rv.status_code == 200
    assert "great-value" in json.loads(rv.data)["tags"]


def test_add_tag_not_found(client):
    assert client.post("/api/recommendations/9999/tags",
                       data={"tag": "x"}).status_code == 404


def test_delete_recommendation(client):
    assert client.delete("/api/recommendations/1").status_code == 200


# ── Agentic chat endpoint ──────────────────────────────────────────────────

def test_chat_requires_fields(client):
    assert client.post("/api/chat", json={}).status_code == 400


def test_chat_session_not_found(client):
    rv = client.post("/api/chat", json={"session_id": 9999, "message": "hi"})
    assert rv.status_code == 404


def test_chat_offline_falls_back_but_still_answers(client):
    """With no Ollama reachable the loop must still persist a reply."""
    before = len(json.loads(client.get("/api/sessions/2/messages").data))
    rv = client.post("/api/chat",
                     json={"session_id": 2, "message": "cheap phone for my mum"})
    assert rv.status_code == 200
    body = json.loads(rv.data)
    assert body["reply"]
    assert body["meta"]["used_fallback"] is True
    after = len(json.loads(client.get("/api/sessions/2/messages").data))
    assert after == before + 2  # user + ai persisted


def test_chat_valid_model_answer_saves_recommendation(client, fake_ollama):
    rv = client.post("/api/chat",
                     json={"session_id": 3, "message": "laptop for 4K editing"})
    assert rv.status_code == 200
    body = json.loads(rv.data)
    assert body["recommended_product_ids"] == ["LAP-001"]
    assert body["meta"]["used_fallback"] is False
    assert body["saved_recommendation"]["product_ids"] == ["LAP-001"]


def test_chat_htmx_returns_html_fragment(client, fake_ollama):
    rv = client.post("/api/chat",
                     data={"session_id": "3", "message": "laptop for editing"},
                     headers={"HX-Request": "true"})
    assert rv.status_code == 200
    assert b"msg--ai" in rv.data
    assert b"hx-swap-oob" in rv.data


# ── HTMX partials ──────────────────────────────────────────────────────────

def test_partial_session_list(client):
    rv = client.get("/partials/session-list")
    assert rv.status_code == 200
    assert b"session-item" in rv.data


def test_partial_chat_panel(client):
    rv = client.get("/partials/chat/1")
    assert rv.status_code == 200
    assert b"chat-messages" in rv.data
    assert b"Clear history" in rv.data


def test_partial_recommendations(client):
    rv = client.get("/partials/recommendations/1")
    assert rv.status_code == 200
    assert b"reco" in rv.data


def test_stylesheet_served(client):
    rv = client.get("/static/style.css")
    assert rv.status_code == 200
    assert b".panel" in rv.data
    assert b"--primary" in rv.data
