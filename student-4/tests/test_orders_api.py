import requests

BASE_URL = "http://127.0.0.1:5004"

NEW_ORDER = {
    "user_id": 999,
    "fulfillment_status": "Pending",
    "items": [
        {"product_id": 701, "product_name": "Test Dishwasher", "category": "Kitchen", "quantity": 2, "unit_price": 500.00}
    ]
}

# --- Health + Read (orders.db) ---

def test_health():
    res = requests.get(f"{BASE_URL}/api/health", timeout=3)
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == "student-4"
    assert data["status"] == "healthy"

def test_get_all_orders_count():
    res = requests.get(f"{BASE_URL}/api/orders", timeout=3)
    assert res.status_code == 200
    orders = res.json()
    assert isinstance(orders, list)
    assert len(orders) >= 10, "Database must have at least 10 seeded appliance orders"

def test_get_single_order_details():
    res = requests.get(f"{BASE_URL}/api/orders/1", timeout=3)
    assert res.status_code == 200
    order = res.json()
    assert order["order_id"] == 1
    assert len(order["line_items"]) >= 1

def test_order_not_found():
    res = requests.get(f"{BASE_URL}/api/orders/9999", timeout=3)
    assert res.status_code == 404

def test_get_saved_cart():
    res = requests.get(f"{BASE_URL}/api/carts/1", timeout=3)
    assert res.status_code == 200
    assert len(res.json()["items"]) >= 1

# --- CRUD: Create -> Read -> Update -> Delete ---

def test_order_crud_lifecycle():
    # CREATE
    res = requests.post(f"{BASE_URL}/api/orders", json=NEW_ORDER, timeout=3)
    assert res.status_code == 201
    order = res.json()
    order_id = order["order_id"]
    assert order["total_price"] == 1000.00
    assert order["line_items"][0]["product_name"] == "Test Dishwasher"

    # READ
    res = requests.get(f"{BASE_URL}/api/orders/{order_id}", timeout=3)
    assert res.status_code == 200

    # UPDATE
    res = requests.put(f"{BASE_URL}/api/orders/{order_id}", json={"fulfillment_status": "Shipped"}, timeout=3)
    assert res.status_code == 200
    assert res.json()["fulfillment_status"] == "Shipped"

    # DELETE
    res = requests.delete(f"{BASE_URL}/api/orders/{order_id}", timeout=3)
    assert res.status_code == 200
    assert requests.get(f"{BASE_URL}/api/orders/{order_id}", timeout=3).status_code == 404

def test_create_order_validation():
    res = requests.post(f"{BASE_URL}/api/orders", json={"user_id": 1, "items": []}, timeout=3)
    assert res.status_code == 400

def test_update_invalid_status():
    res = requests.put(f"{BASE_URL}/api/orders/1", json={"fulfillment_status": "Teleported"}, timeout=3)
    assert res.status_code == 400

def test_update_and_delete_missing_order():
    assert requests.put(f"{BASE_URL}/api/orders/9999", json={"fulfillment_status": "Shipped"}, timeout=3).status_code == 404
    assert requests.delete(f"{BASE_URL}/api/orders/9999", timeout=3).status_code == 404

# --- Cart page (HTMX) ---

def test_index_page():
    res = requests.get(f"{BASE_URL}/", timeout=3)
    assert res.status_code == 200
    assert "OmniTech" in res.text
    assert "Student 4: Cart & Orders" in res.text

def test_cart_view_and_stock_indicators():
    requests.post(f"{BASE_URL}/api/cart/reset", timeout=3)
    res = requests.get(f"{BASE_URL}/api/cart/view", timeout=3)
    assert res.status_code == 200
    assert "stock-dot in-stock" in res.text
    assert "stock-dot out-of-stock" in res.text
    assert "Samsung Fridge 500L" in res.text

def test_cart_quantity_modification():
    res = requests.post(f"{BASE_URL}/api/cart/modify?action=inc&idx=0", timeout=3)
    assert res.status_code == 200
    assert "cart-item-row" in res.text

def test_fulfillment_toggle():
    res = requests.post(f"{BASE_URL}/api/cart/fulfillment?mode=pickup", timeout=3)
    assert res.status_code == 200
    assert "Store Pick Up" in res.text

def test_order_history_endpoint():
    res = requests.get(f"{BASE_URL}/api/orders/history", timeout=3)
    assert res.status_code == 200
    assert "Order #" in res.text
    assert "status-select" in res.text

# CHECKOUT TEST: the order must really be saved in orders.db
def test_checkout_saves_order():
    requests.post(f"{BASE_URL}/api/cart/reset", timeout=3)
    before = len(requests.get(f"{BASE_URL}/api/orders", timeout=3).json())

    res = requests.post(f"{BASE_URL}/api/cart/checkout", timeout=3)
    assert res.status_code == 200
    assert "Order Successfully Placed" in res.text

    orders = requests.get(f"{BASE_URL}/api/orders", timeout=3).json()
    assert len(orders) == before + 1
    new_order = orders[-1]
    assert f"#{new_order['order_id']}" in res.text

    # clean up so the demo data stays the same
    requests.delete(f"{BASE_URL}/api/orders/{new_order['order_id']}", timeout=3)
    requests.post(f"{BASE_URL}/api/cart/reset", timeout=3)

# AI HELPER TEST: allow time for the local LLM, and confirm it really answered
def test_ai_helper_custom_question():
    res = requests.post(
        f"{BASE_URL}/api/orders/ai-validate-cart",
        data={"question": "What are the dimensions of a 500L fridge in cm and ventilation space needed?"},
        timeout=200
    )
    assert res.status_code == 200
    assert "ai-alert-box error" not in res.text, "AI returned the offline banner instead of an answer"
    assert "How the agent worked" in res.text

# AI HELPER JSON TEST (Release 1): the answer is grounded in the database + RAG
def test_ai_helper_grounded_json():
    requests.post(f"{BASE_URL}/api/cart/reset", timeout=3)
    res = requests.post(
        f"{BASE_URL}/api/orders/ai-validate-cart",
        json={"question": "Can I plug the induction cooktop and air fryer into one 10A power point?"},
        timeout=200
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] in ("verified", "fallback")
    assert body["facts_used"] == 4
    assert body["rag_status"] == "ok", "RAG server not reachable - start ai-services/rag-server/server.py"
    assert body["knowledge"], "RAG returned no store knowledge"

# --- Release 1: JSON endpoints used by the MCP tools ---

def test_cart_json_endpoint():
    requests.post(f"{BASE_URL}/api/cart/reset", timeout=3)
    body = requests.get(f"{BASE_URL}/api/cart", timeout=3).json()
    assert body["user_id"] == 101 and len(body["items"]) == 4

def test_product_specs_endpoint():
    body = requests.get(f"{BASE_URL}/api/products/specs?ids=511,9999", timeout=3).json()
    assert body["specs"][0]["product_name"] == "Samsung Fridge 500L"
    assert body["missing"] == [9999]

# MCP LIVE TEST: needs the shared MCP server running (ai-services/mcp-server/server.py)
def test_mcp_order_lookup_live():
    res = requests.post(f"{BASE_URL}/api/mcp/order-status", data={"order_id": "1"}, timeout=30)
    assert "MCP server offline" not in res.text, "start ai-services/mcp-server/server.py first"
    assert "ai-alert-box success" in res.text and "Order #1" in res.text

# RAG LIVE TEST: needs the shared RAG server (ai-services/rag-server/server.py) and Ollama
def test_rag_card_live():
    ok = requests.post(f"{BASE_URL}/api/rag/ask", data={"question": "What is your return policy?"}, timeout=200).text
    assert "RAG server offline" not in ok, "start ai-services/rag-server/server.py first"
    assert "ai-alert-box success" in ok and "Confidence:" in ok and "rag-citations" in ok
    none = requests.post(f"{BASE_URL}/api/rag/ask", data={"question": "Who won the football last night?"}, timeout=200).text
    assert "Insufficient context" in none
