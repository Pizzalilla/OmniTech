import json
import os
import tempfile
import pytest
import sys
from unittest.mock import patch


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
    # 1. Execute the delete request (Customer 1 already exists via seed_db)
    rv = client.delete("/customers/1")
    assert rv.status_code == 200
    
    # 2. Verify the deletion occurred using your database module
    conn = database.get_db()
    # Adjust table name "Customers" below if your table is named differently
    customer = conn.execute("SELECT id FROM Customers WHERE id = 1").fetchone()
    conn.close()
    
    assert customer is None

@patch('main.requests.post') 
def test_generate_ai_suggestions(mock_post, client):
    # 1. Mock the new Multi-Agent Server JSON payload
    mock_post.return_value.status_code = 201
    mock_post.return_value.json.return_value = {
        "id": "wf-test1234",
        "status": "awaiting_human",
        "student": "student-2",
        "review": {"verdict": "pass"}
    }
    
    # 2. Execute the post request
    rv = client.post("/generate-ai-suggestions", data={"customer_id": "1"})
    
    assert rv.status_code == 200
    # 3. Release 2 now shows the human review warning, NOT the final tags
    assert b"Waiting for human approval" in rv.data
    assert b"wf-test1234" in rv.data

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