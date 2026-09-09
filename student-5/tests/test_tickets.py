import pytest
import requests

BACKEND_URL = "http://127.0.0.1:5000"
DB_URL = "http://127.0.0.1:5006"

def test_db_health():
    result = requests.get(f"{DB_URL}/", timeout=3)
    assert result.status_code == 200
    data = result.json()
    assert data["service"] == "student-5-database"
    assert data["status"] == "running"

def test_get_tickets():
    result = requests.get(f"{DB_URL}/tickets", timeout=3)
    assert result.status_code == 200
    tickets = result.json()
    assert isinstance(tickets, list)
    assert len(tickets) >= 10, "Database must have at least 10 seeded tickets"

def test_get_ticket():
    result = requests.get(f"{DB_URL}/tickets/1", timeout=3)
    assert result.status_code == 200
    ticket = result.json()
    print("DEBUG RESPONSE:", ticket)
    assert ticket["ticket_id"] == 1
    assert ticket["product_category"] == "CPU"

def test_updated_ticket():
    result = requests.get(f"{DB_URL}/tickets/1", timeout=3)
    assert result.status_code == 200
    ticket = result.json()
    print("DEBUG RESPONSE:", ticket)
    assert ticket["ticket_id"] == 1
    assert ticket["ai_decision"] is not None
    assert ticket["ai_reasoning"] is not None
    assert ticket["ticket_status"] == "Approved"

def test_create_ticket():
    data = {
        "order_id": 10,
        "ticket_claim": "Pytest Ticket Create Test"
    }
    result = requests.post(
        f"{BACKEND_URL}/tickets/create",
        json=data,
        timeout=3
    )
    assert result.status_code == 201
    response = result.json()
    print("DEBUG RESPONSE:", response)
    assert response["success"] is True