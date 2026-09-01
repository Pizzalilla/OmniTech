import pytest
import requests

DB_URL = "http://127.0.0.1:5004"
BACKEND_URL = "http://127.0.0.1:5014"

# --- Database Service Contract Tests (Port 5004) ---

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
    assert len(orders) >= 10, "Database must have at least 10 seeded appliance orders"

def test_get_single_order_details():
    res = requests.get(f"{DB_URL}/orders/1", timeout=3)
    assert res.status_code == 200
    order = res.json()
    assert order["order_id"] == 1
    assert "line_items" in order
    assert len(order["line_items"]) >= 1

def test_order_not_found():
    res = requests.get(f"{DB_URL}/orders/9999", timeout=3)
    assert res.status_code == 404

# --- Backend Customer Cart & AI Helper Tests (Port 5014) ---

def test_backend_index_page():
    res = requests.get(f"{BACKEND_URL}/", timeout=3)
    assert res.status_code == 200
    assert "OmniTech" in res.text
    assert "Student 4: Cart & Orders" in res.text

def test_backend_cart_view_and_stock_indicators():
    res = requests.get(f"{BACKEND_URL}/api/cart/view", timeout=3)
    assert res.status_code == 200
    # Confirms green in-stock and red out-of-stock dot rendering
    assert "stock-dot in-stock" in res.text
    assert "stock-dot out-of-stock" in res.text
    assert "French Door Smart Refrigerator 600L" in res.text

def test_cart_quantity_modification():
    # Test incrementing first item quantity
    res = requests.post(f"{BACKEND_URL}/api/cart/modify?action=inc&idx=0", timeout=3)
    assert res.status_code == 200
    assert "cart-item-row" in res.text

def test_fulfillment_toggle():
    res = requests.post(f"{BACKEND_URL}/api/cart/fulfillment?mode=pickup", timeout=3)
    assert res.status_code == 200
    assert "Store Pick Up" in res.text

def test_order_history_endpoint():
    res = requests.get(f"{BACKEND_URL}/api/orders/history", timeout=3)
    assert res.status_code == 200
    assert "Order #" in res.text

def test_ai_helper_custom_question():
    res = requests.post(
        f"{BACKEND_URL}/api/orders/ai-validate-cart",
        data={"question": "Do I need a plumber for this fridge?"},
        timeout=15
    )
    assert res.status_code == 200
    assert "ai-alert-box" in res.text
