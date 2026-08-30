import sys
import os
import json
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "database"))

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

from main import app
from database import init_db, seed_db


@pytest.fixture
def client():
    app.config["TESTING"] = True
    init_db()
    seed_db()
    with app.test_client() as c:
        yield c


def test_index_page(client):
    rv = client.get("/")
    assert rv.status_code == 200
    assert b"AI Product Consultant" in rv.data


def test_list_sessions(client):
    rv = client.get("/api/sessions")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert len(data) >= 10


def test_create_session(client):
    rv = client.post(
        "/api/sessions",
        data=json.dumps({"title": "Test Session"}),
        content_type="application/json",
    )
    assert rv.status_code == 201
    data = json.loads(rv.data)
    assert data["title"] == "Test Session"


def test_get_session(client):
    rv = client.get("/api/sessions/1")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert "session" in data
    assert "messages" in data
    assert "recommendations" in data


def test_get_session_not_found(client):
    rv = client.get("/api/sessions/9999")
    assert rv.status_code == 404


def test_update_session_title(client):
    rv = client.put(
        "/api/sessions/1",
        data=json.dumps({"title": "Updated Title"}),
        content_type="application/json",
    )
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data["title"] == "Updated Title"


def test_update_session_no_title(client):
    rv = client.put(
        "/api/sessions/1",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert rv.status_code == 400


def test_delete_session(client):
    rv = client.post(
        "/api/sessions",
        data=json.dumps({"title": "To Delete"}),
        content_type="application/json",
    )
    session_id = json.loads(rv.data)["id"]
    rv = client.delete(f"/api/sessions/{session_id}")
    assert rv.status_code == 200
    rv = client.get(f"/api/sessions/{session_id}")
    assert rv.status_code == 404


def test_delete_session_not_found(client):
    rv = client.delete("/api/sessions/9999")
    assert rv.status_code == 404


def test_update_recommendation_tags(client):
    rv = client.put(
        "/api/recommendations/1/tags",
        data=json.dumps({"tags": "new-tag,updated"}),
        content_type="application/json",
    )
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert "new-tag" in data["tags"]


def test_update_recommendation_not_found(client):
    rv = client.put(
        "/api/recommendations/9999/tags",
        data=json.dumps({"tags": "test"}),
        content_type="application/json",
    )
    assert rv.status_code == 404


def test_log_recommendation(client):
    rv = client.post(
        "/api/chat/recommend",
        data=json.dumps({
            "session_id": 1,
            "product_name": "Test Product",
            "category": "Testing",
            "recommendation_text": "Great for tests",
        }),
        content_type="application/json",
    )
    assert rv.status_code == 201
    data = json.loads(rv.data)
    assert data["product_name"] == "Test Product"


def test_log_recommendation_missing_fields(client):
    rv = client.post(
        "/api/chat/recommend",
        data=json.dumps({"session_id": 1}),
        content_type="application/json",
    )
    assert rv.status_code == 400


def test_chat_missing_fields(client):
    rv = client.post(
        "/api/chat",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert rv.status_code == 400


def test_chat_session_not_found(client):
    rv = client.post(
        "/api/chat",
        data=json.dumps({"session_id": 9999, "message": "hello"}),
        content_type="application/json",
    )
    assert rv.status_code == 404


def test_partial_session_list(client):
    rv = client.get("/partials/session-list")
    assert rv.status_code == 200
    assert b"session-tab" in rv.data


def test_partial_chat(client):
    rv = client.get("/partials/chat/1")
    assert rv.status_code == 200
    assert b"chat-messages" in rv.data
