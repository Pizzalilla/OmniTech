import json
import os
import tempfile
import pytest
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "database"))

import database
from main import app

@pytest.fixture
def client(tmp_path):
    database.DB_PATH = str(tmp_path / "test.db")
    database.init_db()
    database.seed_db()
    app.config["TESTING"] = True

    with app.test_client() as c:
        yield c

def test_index_page(client):
    rv = client.get("/")
    assert rv.status_code == 200
    assert b"Customer Profiles &amp; Preferences" in rv.data or b"Customer Profiles & Preferences" in rv.data

def test_create_customer(client):
    rv = client.post("/customers", data={
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane.smith@example.com",
        "phone": "0400000000"
    })
    
    assert rv.status_code == 200
    assert b"Created customer profile" in rv.data

def test_update_customer(client):
    rv = client.put("/customers/1", data={
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com"
    })
    assert rv.status_code == 200
    assert b"John Doe" in rv.data

    rv_invalid = client.put("/customers/1", data={
        "first_name": "",
        "last_name": "Doe",
        "email": "alexander.mercer@example.com"
    })
    assert rv_invalid.status_code == 200
    assert "showValidationAlert" in rv_invalid.headers.get("HX-Trigger", "")


def test_delete_customer(client):
    rv = client.delete("/customers/1")
    assert rv.status_code == 200

def test_generate_ai_suggestions(client):
    rv = client.post("/generate-ai-suggestions", data={"customer_id": "1"})
    assert rv.status_code == 200
    assert b"Apply Suggestions to Profile" in rv.data

def test_apply_tags(client):
    rv = client.post("/apply-tags", data={"customer_id": "1", "tags": "4k-video-editing"})
    assert rv.status_code == 200
    assert b"Applied Suggestions to Profile" in rv.data

def test_delete_preference_tag(client):
    client.post("/apply-tags", data={"customer_id": "1", "tags": "4k-video-editing"})

    conn = database.get_db()
    tag = conn.execute("SELECT id FROM PreferenceTags WHERE customer_id = 1 AND tag_name = '4k-video-editing'").fetchone()
    conn.close()

    assert tag is not None
    tag_id = tag["id"]

    rv = client.delete(f"/customers/1/tags/{tag_id}")
    assert rv.status_code == 200
    assert b"4k-video-editing" not in rv.data