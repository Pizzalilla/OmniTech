import pytest
import requests

DB_URL = "http://localhost:5004"
BACKEND_URL = "http://localhost:5014"

# --- Database Service Tests (Port 5004) ---

def test_db_health():
    res = requests.get(f"{DB_URL}/", timeout=3)
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == "student-4-database"
    assert data["status"] == "healthy"

def test_get_all_orders_count():
    res = requests.get(f"{DB_URL}/orders", timeout=3)
    assert res.status_code == 200
    orders = res.json()
    assert isinstance(orders, list)
    assert len(orders) >= 10, "Database must have at least 10 seeded orders"

def test_get_single_order_details():
    res = requests.get(f"{DB_URL}/orders/1", timeout=3)
    assert res.status_code == 200
    order = res.json()
    assert order["order_id"] == 1
    assert "line_items" in order
    assert len(order["line_items"]) >= 1

def test_get_cart_items():
    res = requests.get(f"{DB_URL}/carts/1", timeout=3)
    assert res.status_code == 200
    cart = res.json()
    assert cart["cart_id"] == 1
    assert "items" in cart
    assert len(cart["items"]) >= 1

def test_order_not_found():
    res = requests.get(f"{DB_URL}/orders/9999", timeout=3)
    assert res.status_code == 404

# --- Backend Service Tests (Port 5014) ---

def test_backend_index_page():
    res = requests.get(f"{BACKEND_URL}/", timeout=3)
    assert res.status_code == 200
    assert "Student 4: Cart & Order Processing" in res.text

def test_backend_cart_html_fragment():
    res = requests.get(f"{BACKEND_URL}/api/cart/1", timeout=3)
    assert res.status_code == 200
    assert "order-list" in res.text

def test_backend_orders_list_fragment():
    res = requests.get(f"{BACKEND_URL}/api/orders/list", timeout=3)
    assert res.status_code == 200
    assert "Order #" in res.text

def test_ai_validate_cart_endpoint():
    res = requests.post(
        f"{BACKEND_URL}/api/orders/ai-validate-cart",
        data={"cart_items": "French Door Smart Refrigerator 600L"},
        timeout=15
    )
    assert res.status_code == 200
    # Must either return AI analysis or the handled fallback message
    assert "ai-response" in res.text or "AI Error" in res.text
