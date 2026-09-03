import pytest
import requests

DB_URL = "http://127.0.0.1:5005"

def test_db_health():
    result = requests.get(f"{DB_URL}/", timeout=3)
    assert result.status_code == 200
    data = result.json()
    assert data["service"] == "student-4-database"
    assert data["status"] == "healthy"

def test_get_tickets():
    result = requests.get(f"{DB_URL}/tickets", timeout=3)
    assert result.status_code == 200
    tickets = result.json()
    assert isinstance(tickets, list)
    assert len(tickets) >= 10, "Database must have at least 10 seeded tickets"