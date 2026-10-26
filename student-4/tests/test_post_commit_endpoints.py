"""
Release 2 post-commit endpoint tests (run by .github/workflows/student-4.yml).

The two Student 4 backend endpoint functions under test:
    1. create_order  ->  POST /api/orders
    2. update_order  ->  PUT  /api/orders/<order_id>

These call the running service on port 5004 over HTTP, the same way the
frontend and other services do. CI starts the service first, with all AI
switched off. Every order made here is deleted again at the end.
"""

import pytest
import requests

BASE_URL = "http://127.0.0.1:5004"

NEW_ORDER = {
    "user_id": 101,
    "fulfillment_status": "Pending",
    "items": [
        {"product_id": 511, "product_name": "Samsung Fridge 500L", "category": "Kitchen",
         "quantity": 1, "unit_price": 1499.00},
        {"product_id": 514, "product_name": "Air Fryer 20L", "category": "Small Appliances",
         "quantity": 2, "unit_price": 189.00},
    ],
}


# FIXTURE: one order made through the API, removed after the test
@pytest.fixture
def order():
    resp = requests.post(f"{BASE_URL}/api/orders", json=NEW_ORDER, timeout=5)
    assert resp.status_code == 201
    created = resp.json()
    yield created
    requests.delete(f"{BASE_URL}/api/orders/{created['order_id']}", timeout=5)


# ---------------------------------------------------------------------------
# ENDPOINT 1: POST /api/orders (create_order)
# ---------------------------------------------------------------------------

def test_create_order_returns_201_with_saved_order(order):
    assert order["order_id"] > 0
    assert order["user_id"] == 101
    assert order["fulfillment_status"] == "Pending"
    assert len(order["line_items"]) == 2


def test_create_order_works_out_the_total(order):
    # 1 x 1499.00 + 2 x 189.00
    assert order["total_price"] == pytest.approx(1877.00)


def test_created_order_can_be_read_back(order):
    resp = requests.get(f"{BASE_URL}/api/orders/{order['order_id']}", timeout=5)
    assert resp.status_code == 200
    assert resp.json()["order_id"] == order["order_id"]


@pytest.mark.parametrize("bad_body, reason", [
    ({"items": NEW_ORDER["items"]}, "no user_id"),
    ({"user_id": 101, "items": []}, "no items"),
    ({**NEW_ORDER, "fulfillment_status": "Teleported"}, "unknown status"),
    ({"user_id": 101, "items": [{"product_id": 511, "quantity": 1}]}, "item missing fields"),
])
def test_create_order_rejects_bad_input(bad_body, reason):
    resp = requests.post(f"{BASE_URL}/api/orders", json=bad_body, timeout=5)
    assert resp.status_code == 400, reason
    assert "error" in resp.json()


# ---------------------------------------------------------------------------
# ENDPOINT 2: PUT /api/orders/<order_id> (update_order)
# ---------------------------------------------------------------------------

def test_update_order_changes_status(order):
    resp = requests.put(f"{BASE_URL}/api/orders/{order['order_id']}",
                        json={"fulfillment_status": "Shipped"}, timeout=5)
    assert resp.status_code == 200
    assert resp.json()["fulfillment_status"] == "Shipped"


def test_update_order_is_saved(order):
    requests.put(f"{BASE_URL}/api/orders/{order['order_id']}",
                 json={"fulfillment_status": "Completed"}, timeout=5)
    saved = requests.get(f"{BASE_URL}/api/orders/{order['order_id']}", timeout=5).json()
    assert saved["fulfillment_status"] == "Completed"


def test_update_order_rejects_unknown_status(order):
    resp = requests.put(f"{BASE_URL}/api/orders/{order['order_id']}",
                        json={"fulfillment_status": "Lost"}, timeout=5)
    assert resp.status_code == 400
    saved = requests.get(f"{BASE_URL}/api/orders/{order['order_id']}", timeout=5).json()
    assert saved["fulfillment_status"] == "Pending"


def test_update_missing_order_returns_404():
    resp = requests.put(f"{BASE_URL}/api/orders/999999",
                        json={"fulfillment_status": "Shipped"}, timeout=5)
    assert resp.status_code == 404
