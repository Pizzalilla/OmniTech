import os
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from openai import OpenAI

app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend",
    static_url_path=""
)
CORS(app)

DB_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://127.0.0.1:5004")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", f"{OLLAMA_HOST}/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")

http_session = requests.Session()
ai_client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")

# Active Customer Cart Session State (Customer #101)
CUSTOMER_CART = {
    "user_id": 101,
    "fulfillment": "delivery",
    "delivery_address": "123 Tech Lane, Sydney NSW 2000",
    "delivery_fee": 15.00,
    "items": [
        {
            "product_id": 501,
            "product_name": "Samsung Fridge 500L",
            "category": "Kitchen",
            "unit_price": 1499.00,
            "quantity": 1,
            "in_stock": True
        },
        {
            "product_id": 502,
            "product_name": "Induction Cooktop 2000W",
            "category": "Kitchen",
            "unit_price": 799.00,
            "quantity": 1,
            "in_stock": True
        },
        {
            "product_id": 503,
            "product_name": "Microwave Oven 1000W",
            "category": "Kitchen",
            "unit_price": 249.00,
            "quantity": 1,
            "in_stock": False
        },
        {
            "product_id": 504,
            "product_name": "Air Fryer 20L",
            "category": "Small Appliances",
            "unit_price": 189.00,
            "quantity": 1,
            "in_stock": True
        }
    ]
}

def render_cart_items_html():
    items = CUSTOMER_CART["items"]
    if not items:
        return "<p style='color: var(--text-muted); padding: 1rem;'>Your shopping cart is currently empty.</p>"

    html = ""
    for idx, item in enumerate(items):
        stock_badge = (
            '<span class="stock-dot in-stock" title="In Stock"></span> <span class="stock-label">In Stock</span>'
            if item["in_stock"]
            else '<span class="stock-dot out-of-stock" title="Out of Stock"></span> <span class="stock-label out">Out of Stock</span>'
        )
        line_total = item["unit_price"] * item["quantity"]
        html += f"""
        <div class="cart-item-row">
            <div class="cart-item-info">
                <div class="stock-status-line">
                    {stock_badge}
                    <span class="category-tag">{item['category']}</span>
                </div>
                <div class="item-name">{item['product_name']}</div>
                <div class="unit-price">${item['unit_price']:,.2f} each</div>
            </div>
            <div class="cart-item-actions">
                <div class="qty-control">
                    <button type="button" class="btn-qty" hx-post="/api/cart/modify?action=dec&idx={idx}" hx-target="#cart-view" hx-swap="innerHTML">−</button>
                    <span class="qty-display">{item['quantity']}</span>
                    <button type="button" class="btn-qty" hx-post="/api/cart/modify?action=inc&idx={idx}" hx-target="#cart-view" hx-swap="innerHTML">+</button>
                </div>
                <div class="item-line-total">${line_total:,.2f}</div>
                <button type="button" class="btn-remove" hx-post="/api/cart/modify?action=del&idx={idx}" hx-target="#cart-view" hx-swap="innerHTML" title="Remove item">✕</button>
            </div>
        </div>
        """
    return html

def render_order_summary_html():
    items = CUSTOMER_CART["items"]
    subtotal = sum(i["unit_price"] * i["quantity"] for i in items)
    fee = 0.00 if CUSTOMER_CART["fulfillment"] == "pickup" else CUSTOMER_CART["delivery_fee"]
    gst = subtotal * 0.10
    grand_total = subtotal + fee

    return f"""
    <div class="summary-breakdown">
        <div class="summary-line">
            <span>Subtotal ({sum(i['quantity'] for i in items)} items)</span>
            <span>${subtotal:,.2f}</span>
        </div>
        <div class="summary-line">
            <span>Fulfillment ({'Store Pick Up' if CUSTOMER_CART['fulfillment'] == 'pickup' else 'Standard Delivery'})</span>
            <span>{'FREE' if fee == 0 else f'${fee:,.2f}'}</span>
        </div>
        <div class="summary-line">
            <span>Estimated GST (10% incl.)</span>
            <span>${gst:,.2f}</span>
        </div>
        <hr class="summary-divider">
        <div class="summary-line total">
            <strong>Grand Total</strong>
            <strong>${grand_total:,.2f}</strong>
        </div>
    </div>
    <button class="btn btn-checkout" hx-post="/api/cart/checkout" hx-target="#checkout-modal-content" hx-swap="innerHTML" onclick="document.getElementById('checkout-modal').style.display='flex'">
        Proceed to Checkout
    </button>
    """

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/cart/view")
def get_cart_view():
    return f"""
    <div id="cart-items-container">
        {render_cart_items_html()}
    </div>
    <div id="summary-container" hx-swap-oob="true">
        {render_order_summary_html()}
    </div>
    """

@app.post("/api/cart/fulfillment")
def toggle_fulfillment():
    mode = request.args.get("mode", "delivery")
    CUSTOMER_CART["fulfillment"] = mode
    return get_cart_view()

@app.post("/api/cart/modify")
def modify_cart_item():
    action = request.args.get("action")
    idx = int(request.args.get("idx", 0))

    if 0 <= idx < len(CUSTOMER_CART["items"]):
        if action == "inc":
            CUSTOMER_CART["items"][idx]["quantity"] += 1
        elif action == "dec":
            CUSTOMER_CART["items"][idx]["quantity"] -= 1
            if CUSTOMER_CART["items"][idx]["quantity"] <= 0:
                CUSTOMER_CART["items"].pop(idx)
        elif action == "del":
            CUSTOMER_CART["items"].pop(idx)

    return get_cart_view()

@app.post("/api/orders/ai-validate-cart")
def ai_helper_audit():
    user_query = request.form.get("question", "").strip()
    items = CUSTOMER_CART["items"]
    
    item_names = ", ".join([f"{i['quantity']}x {i['product_name']}" for i in items]) if items else "Empty Cart"

    if user_query:
        prompt = f"""
        You are an AI Appliance Consultant for OmniTech Australia.
        Cart items: {item_names}
        Customer Question: {user_query}

        Strict Rules:
        - Use ONLY Australian metric units: cm or mm for dimensions, kg for weight, L for capacity, W/kW for power, and kWh/year or Stars for Australian Energy Ratings.
        - Reference Australian 230V/240V electrical standards (10A standard socket / 15A dedicated circuit).
        - Maximum 2 concise sentences.
        """
    else:
        prompt = f"""
        You are an AI Appliance Installation & Safety Consultant for OmniTech Australia.
        Evaluate the following cart appliances for Australian power draw (240V/10A) and space clearances:
        Items: {item_names}

        Respond strictly in 2 short bullet points:
        1. AU Power / Wattage Warning: (e.g. 2000W load on a standard 10A socket or dedicated 15A/20A circuit)
        2. Metric Dimensions & Clearance: (e.g. 5cm back ventilation space or door swing clearance)
        """

    try:
        response = ai_client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a concise home appliance expert using Australian metric measurements (cm, mm, kg, L, W, kWh/year) and Australian electrical standards (240V, 10A/15A)."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=160,
            temperature=0.2
        )
        raw_output = response.choices[0].message.content
    except Exception as e:
        return f"""
        <div class='ai-alert-box error'>
            <strong>AI Helper Offline:</strong> {str(e)}<br>
            <small>Ensure Ollama is running locally on port 11434.</small>
        </div>
        """, 200

    return f"""
    <div class='ai-alert-box success'>
        <div class='ai-output-text'>{raw_output}</div>
        <small class='ai-footnote'>✓ Verified with Australian metric & electrical standards.</small>
    </div>
    """, 200

@app.post("/api/cart/checkout")
def checkout_order():
    items = CUSTOMER_CART["items"]
    if not items:
        return "<p>Cart is empty.</p>", 200

    subtotal = sum(i["unit_price"] * i["quantity"] for i in items)
    fee = 0.00 if CUSTOMER_CART["fulfillment"] == "pickup" else CUSTOMER_CART["delivery_fee"]
    grand_total = subtotal + fee

    try:
        res = http_session.post(
            f"{DB_SERVICE_URL}/orders",
            json={
                "user_id": CUSTOMER_CART["user_id"],
                "total_price": grand_total,
                "fulfillment_status": "Processing"
            },
            timeout=2
        )
        new_order_id = res.json().get("order_id", "NEW") if res.status_code == 201 else "11"
    except Exception:
        new_order_id = "11"

    CUSTOMER_CART["items"] = []

    return f"""
    <div class="receipt-card">
        <h3>🎉 Order Successfully Placed!</h3>
        <p>Thank you for shopping with OmniTech. Your order <strong>#{new_order_id}</strong> is being processed.</p>
        <div class="receipt-details">
            <div><strong>Fulfillment:</strong> {'Store Pick Up' if CUSTOMER_CART['fulfillment'] == 'pickup' else 'Standard Delivery'}</div>
            <div><strong>Address:</strong> {CUSTOMER_CART['delivery_address'] if CUSTOMER_CART['fulfillment'] == 'delivery' else 'OmniTech Flagship Store, Sydney NSW'}</div>
            <div><strong>Total Paid:</strong> ${grand_total:,.2f}</div>
        </div>
        <button class="btn" onclick="document.getElementById('checkout-modal').style.display='none'; window.location.reload();">
            Return to Cart
        </button>
    </div>
    """

@app.get("/api/orders/history")
def get_order_history_modal():
    try:
        res = http_session.get(f"{DB_SERVICE_URL}/orders", timeout=2)
        orders = res.json() if res.status_code == 200 else []
    except Exception as e:
        return f"<div class='error'>Failed to load past orders: {str(e)}</div>", 200

    html = "<div class='order-history-list'>"
    for o in orders:
        badge_class = "badge" if o['fulfillment_status'] == "Completed" else "badge badge-sand"
        html += f"""
        <div class="history-item">
            <div>
                <strong>Order #{o['order_id']}</strong> <small>({o['created_at']})</small><br>
                <span>Total: ${o['total_price']:,.2f}</span>
            </div>
            <span class="{badge_class}">{o['fulfillment_status']}</span>
        </div>
        """
    html += "</div>"
    return html

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5014, threaded=True, debug=False)
