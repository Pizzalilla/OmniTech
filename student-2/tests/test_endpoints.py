import sys
import os
import pytest
from unittest.mock import patch

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

from main import app 

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

# --- GET /customers Tests ---

def test_get_customers_success(client):
    """Test successful retrieval of the customer list."""
    with patch("main.get_db") as mock_db:

        mock_db.return_value.execute.return_value.fetchall.return_value = [
            {"id": 1, "first_name": "Alice", "last_name": "Smith", "email": "alice@example.com"}
        ]
        
        response = client.get("/customers")
        assert response.status_code == 200
        assert b"Alice" in response.data
        assert b"Smith" in response.data

def test_get_customers_htmx_format(client):
    """Test that the endpoint returns proper HTML/HTMX structure."""
    with patch("main.get_db") as mock_db:
        mock_db.return_value.execute.return_value.fetchall.return_value = []
        
        response = client.get("/customers")
        assert response.status_code == 200
        assert b"<table class='data-table'" in response.data

# --- POST /api/staff/workflow/<id>/decision Tests ---

@patch("main.requests.post")
def test_submit_workflow_approve_success(mock_post, client):
    """Test approving a workflow."""
    mock_post.return_value.status_code = 200
    
    response = client.post(
        "/api/staff/workflow/wf_123/decision",
        data={
            "decision": "approve",
            "note": "",
            "corrected_answer": ""
        }
    )
    
    assert response.status_code == 200
    assert b"Success" in response.data

@patch("main.requests.post")
def test_submit_workflow_hx_headers(mock_post, client):
    """Test that the correct HTMX trigger headers are sent back for UI sync."""
    mock_post.return_value.status_code = 200
    
    response = client.post(
        "/api/staff/workflow/wf_123/decision",
        data={"decision": "approve"}
    )
    
    assert response.status_code == 200

    assert "refreshPendingList" in response.headers.get("HX-Trigger", "")
    assert "refreshCustomers" in response.headers.get("HX-Trigger", "")

@patch("main.requests.post")
def test_submit_workflow_invalid_decision(mock_post, client):
    """Test how the app handles an error from the Multi-Agent server."""
    mock_post.return_value.status_code = 400
    mock_post.return_value.json.return_value = {"error": "Invalid decision type"}
    
    response = client.post(
        "/api/staff/workflow/wf_123/decision",
        data={"decision": "destroy_everything"}
    )
    
    assert response.status_code == 200 
    assert b"Error: Invalid decision type" in response.data