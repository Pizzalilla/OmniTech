"""
Release 2 post-commit endpoint tests for Student 5.

Endpoint 1: POST /tickets/create
Endpoint 2: POST /tickets/<ticket_id>/update

Uses the actual backend HTTP endpoints.
No MCP, RAG, Ollama, or Multi-Agent Server is required.
"""

import os
import sys
import uuid
from pathlib import Path

import pytest
import requests

# Running from student-5/tests/
STUDENT5_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDENT5_DIR))

from database.app import get_db_connection


BASE_URL = os.getenv(
    "WARRANTY_RETURNS_BASE_URL",
    "http://127.0.0.1:5000",
)


def get_first_valid_order():
    """Retrieve a real order from the initialised test database."""
    conn = get_db_connection()
    try:
        row = conn.execute("""
            SELECT
                orders.order_id,
                orders.customer_id,
                orders.product_id,
                products.product_category
            FROM orders
            JOIN products
                ON orders.product_id = products.product_id
            ORDER BY orders.order_id
            LIMIT 1
        """).fetchone()
    finally:
        conn.close()

    if row is None:
        pytest.fail(
            "No valid order found. Check that database/init_db.py "
            "initialises the orders and products tables with data."
        )

    return dict(row)


def get_ticket(ticket_id):
    """Read a ticket directly from the application's database."""
    conn = get_db_connection()
    try:
        row = conn.execute("""
            SELECT
                ticket_id,
                customer_id,
                product_id,
                product_category,
                ticket_claim,
                ticket_status,
                ai_decision,
                ai_reasoning
            FROM tickets
            WHERE ticket_id = ?
        """, (ticket_id,)).fetchone()

        return dict(row) if row is not None else None
    finally:
        conn.close()


@pytest.fixture
def ticket():
    """Create a ticket using the actual endpoint and clean it up afterwards."""
    order = get_first_valid_order()
    claim = f"CI endpoint test {uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/tickets/create",
        json={
            "order_id": order["order_id"],
            "ticket_claim": claim,
        },
        timeout=10,
    )

    assert response.status_code == 201, (
        f"Ticket creation failed: "
        f"{response.status_code} {response.text}"
    )

    body = response.json()
    assert body["success"] is True

    # The current endpoint does not return ticket_id, so look it up.
    conn = get_db_connection()
    try:
        row = conn.execute("""
            SELECT ticket_id
            FROM tickets
            WHERE ticket_claim = ?
            ORDER BY ticket_id DESC
            LIMIT 1
        """, (claim,)).fetchone()
    finally:
        conn.close()

    assert row is not None, "Created ticket was not persisted."

    created_ticket_id = row["ticket_id"]

    try:
        yield {
            "ticket_id": created_ticket_id,
            "claim": claim,
            "order": order,
        }
    finally:
        requests.delete(
            f"{BASE_URL}/tickets/{created_ticket_id}/delete",
            timeout=10,
        )


# ------------------------------------------------------------------
# Endpoint 1: POST /tickets/create
# ------------------------------------------------------------------

def test_create_ticket_returns_201_with_ticket_id(ticket):
    saved = get_ticket(ticket["ticket_id"])

    assert saved is not None
    assert saved["ticket_id"] > 0
    assert saved["customer_id"] == ticket["order"]["customer_id"]
    assert saved["product_id"] == ticket["order"]["product_id"]
    assert saved["product_category"] == ticket["order"]["product_category"]


def test_create_ticket_stores_claim(ticket):
    saved = get_ticket(ticket["ticket_id"])

    assert saved is not None
    assert saved["ticket_claim"] == ticket["claim"]
    assert saved["ticket_status"] == "Pending"


@pytest.mark.parametrize(
    "body",
    [
        {"ticket_claim": "Missing order ID"},
        {"order_id": 1},
        {"order_id": 1, "ticket_claim": ""},
    ],
)
def test_create_ticket_rejects_missing_fields(body):
    response = requests.post(
        f"{BASE_URL}/tickets/create",
        json=body,
        timeout=10,
    )

    assert response.status_code == 400
    assert "error" in response.json()


def test_create_ticket_rejects_unknown_order():
    response = requests.post(
        f"{BASE_URL}/tickets/create",
        json={
            "order_id": 999999999,
            "ticket_claim": "Test with nonexistent order",
        },
        timeout=10,
    )

    assert response.status_code == 404
    assert response.json()["success"] is False


# ------------------------------------------------------------------
# Endpoint 2: POST /tickets/<ticket_id>/update
# ------------------------------------------------------------------

def test_update_ticket_changes_status(ticket):
    response = requests.post(
        f"{BASE_URL}/tickets/{ticket['ticket_id']}/update",
        json={
            "decision": "Approved",
            "reasoning": "Approved by the CI endpoint test.",
        },
        timeout=10,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True


def test_update_ticket_status_is_persisted(ticket):
    ticket_id = ticket["ticket_id"]

    response = requests.post(
        f"{BASE_URL}/tickets/{ticket_id}/update",
        json={
            "decision": "Rejected",
            "reasoning": "Rejected by the CI endpoint test.",
        },
        timeout=10,
    )

    assert response.status_code == 200

    saved = get_ticket(ticket_id)

    assert saved is not None
    assert saved["ticket_status"] == "Rejected"
    assert saved["ai_decision"] == "Rejected"
    assert saved["ai_reasoning"] == (
        "Rejected by the CI endpoint test."
    )


def test_update_ticket_rejects_missing_fields(ticket):
    response = requests.post(
        f"{BASE_URL}/tickets/{ticket['ticket_id']}/update",
        json={"decision": "Approved"},
        timeout=10,
    )

    assert response.status_code == 400
    assert response.json()["success"] is False


def test_update_missing_ticket_returns_404():
    response = requests.post(
        f"{BASE_URL}/tickets/999999999/update",
        json={
            "decision": "Approved",
            "reasoning": "Testing a nonexistent ticket.",
        },
        timeout=10,
    )

    assert response.status_code == 404
    assert response.json()["success"] is False
