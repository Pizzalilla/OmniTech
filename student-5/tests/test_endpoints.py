"""
Release 2 post-commit endpoint tests for the Warranty Returns feature.

The two assumed endpoint functions under test:
    1. create_ticket -> POST /api/tickets
    2. update_ticket -> PUT /api/tickets/<ticket_id>

Tickets use ticket_id, generated automatically by SQLite.
"""

import os

import pytest
import requests


BASE_URL = os.getenv(
    "WARRANTY_RETURNS_BASE_URL",
    "http://127.0.0.1:5005",
)

NEW_TICKET = {
    "customer_id": 101,
    "product_id": 511,
    "product_category": "Kitchen",
    "ticket_claim": (
        "The product stopped working during normal use."
    ),
}


# ---------------------------------------------------------------------------
# FIXTURE: create a ticket and clean it up after the test
# ---------------------------------------------------------------------------

@pytest.fixture
def ticket():
    response = requests.post(
        f"{BASE_URL}/api/tickets",
        json=NEW_TICKET,
        timeout=5,
    )
    assert response.status_code == 201, (
        f"Ticket creation failed: "
        f"{response.status_code} {response.text}"
    )
    created = response.json()
    assert "ticket_id" in created
    yield created
    # Assumes the API exposes DELETE for test cleanup.
    requests.delete(
        f"{BASE_URL}/api/tickets/{created['ticket_id']}",
        timeout=5,
    )


# ---------------------------------------------------------------------------
# ENDPOINT 1: POST /api/tickets (create_ticket)
# ---------------------------------------------------------------------------

def test_create_ticket_returns_201_with_ticket_id(ticket):
    assert ticket["ticket_id"] > 0
    assert ticket["customer_id"] == NEW_TICKET["customer_id"]
    assert ticket["product_id"] == NEW_TICKET["product_id"]
    assert ticket["ticket_claim"] == NEW_TICKET["ticket_claim"]


def test_create_ticket_stores_claim(ticket):
    response = requests.get(
        f"{BASE_URL}/api/tickets/{ticket['ticket_id']}",
        timeout=5,
    )
    assert response.status_code == 200
    saved = response.json()
    assert saved["ticket_id"] == ticket["ticket_id"]
    assert saved["customer_id"] == NEW_TICKET["customer_id"]
    assert saved["product_id"] == NEW_TICKET["product_id"]
    assert saved["ticket_claim"] == NEW_TICKET["ticket_claim"]


@pytest.mark.parametrize(
    "bad_body, reason",
    [
        (
            {
                "product_id": 511,
                "product_category": "Kitchen",
                "ticket_claim": "Product is defective.",
            },
            "missing customer_id",
        ),
        (
            {
                "customer_id": 101,
                "product_category": "Kitchen",
                "ticket_claim": "Product is defective.",
            },
            "missing product_id",
        ),
        (
            {
                "customer_id": 101,
                "product_id": 511,
                "product_category": "Kitchen",
                "ticket_claim": "",
            },
            "missing claim description",
        ),
    ],
)
def test_create_ticket_rejects_invalid_input(bad_body, reason):
    response = requests.post(
        f"{BASE_URL}/api/tickets",
        json=bad_body,
        timeout=5,
    )
    assert response.status_code == 400, reason
    assert "error" in response.json()


# ---------------------------------------------------------------------------
# ENDPOINT 2: PUT /api/tickets/<ticket_id> (update_ticket)
# ---------------------------------------------------------------------------

def test_update_ticket_changes_status(ticket):
    response = requests.put(
        f"{BASE_URL}/api/tickets/{ticket['ticket_id']}",
        json={"ticket_status": "Approved"},
        timeout=5,
    )
    assert response.status_code == 200
    assert response.json()["ticket_status"] == "Approved"


def test_update_ticket_status_is_persisted(ticket):
    ticket_id = ticket["ticket_id"]
    response = requests.put(
        f"{BASE_URL}/api/tickets/{ticket_id}",
        json={"ticket_status": "Rejected"},
        timeout=5,
    )
    assert response.status_code == 200
    saved = requests.get(
        f"{BASE_URL}/api/tickets/{ticket_id}",
        timeout=5,
    )
    assert saved.status_code == 200
    assert saved.json()["ticket_status"] == "Rejected"


def test_update_ticket_rejects_unknown_status(ticket):
    ticket_id = ticket["ticket_id"]
    response = requests.put(
        f"{BASE_URL}/api/tickets/{ticket_id}",
        json={"ticket_status": "Unknown Status"},
        timeout=5,
    )
    assert response.status_code == 400
    saved = requests.get(
        f"{BASE_URL}/api/tickets/{ticket_id}",
        timeout=5,
    )
    assert saved.status_code == 200
    assert saved.json()["ticket_status"] != "Unknown Status"


def test_update_missing_ticket_returns_404():
    response = requests.put(
        f"{BASE_URL}/api/tickets/999999",
        json={"ticket_status": "Approved"},
        timeout=5,
    )
    assert response.status_code == 404
