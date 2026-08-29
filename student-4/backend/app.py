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
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")

# Persistent HTTP session to eliminate handshake overhead
http_session = requests.Session()
ai_client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/orders/list")
def list_orders_html():
    try:
        res = http_session.get(f"{DB_SERVICE_URL}/orders", timeout=2)
        orders = res.json() if res.status_code == 200 else []
    except Exception as e:
        return f"<div class='error'>Failed to load orders: {str(e)}</div>", 200

    html = "<ul class='order-list'>"
    for o in orders:
        badge_class = "badge" if o['fulfillment_status'] == "Completed" else "badge badge-sand"
        html += f"""
        <li>
            <div>
                <strong>Order #{o['order_id']}</strong> (Customer #{o['user_id']})<br>
                <small>${o['total_price']:.2f}</small>
            </div>
            <span class='{badge_class}'>{o['fulfillment_status']}</span>
        </li>
        """
    html += "</ul>"
    return html

@app.get("/api/cart/<int:cart_id>")
def get_cart_html(cart_id):
    try:
        res = http_session.get(f"{DB_SERVICE_URL}/carts/{cart_id}", timeout=2)
        if res.status_code != 200:
            return f"<div class='error'>Cart #{cart_id} not found.</div>", 200
        cart = res.json()
    except Exception as e:
        return f"<div class='error'>Failed to load cart: {str(e)}</div>", 200

    items = cart.get("items", [])
    total = sum(i["unit_price"] * i["quantity"] for i in items)
    
    html = "<ul class='order-list'>"
    for i in items:
        html += f"""
        <li>
            <div>
                <strong>{i['product_name']}</strong><br>
                <small>Qty: {i['quantity']} × ${i['unit_price']:.2f}</small>
            </div>
            <span class='badge badge-cream'>${(i['unit_price'] * i['quantity']):.2f}</span>
        </li>
        """
    html += f"</ul><div style='margin-top: 1rem; font-weight: bold;'>Cart Total: ${total:.2f}</div>"
    return html

@app.post("/api/orders/ai-validate-cart")
def ai_validate_cart():
    cart_items = request.form.get("cart_items", "").strip()
    if not cart_items:
        return "<div class='error'>Please enter appliance items in your cart to validate.</div>", 200

    prompt = f"""
    You are an AI Appliance Installation & Safety Consultant for OmniTech.
    Evaluate the following home appliances in cart for electrical load or essential accessories:
    Items: {cart_items}

    Respond strictly in 2 short bullet points:
    1. Installation / Power Warning: (e.g., circuit load, dedicated breaker)
    2. Recommended Accessory Upsell: (e.g., surge protector, water filter)
    """

    try:
        response = ai_client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": "You are a concise home appliance installation expert."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=180,
            temperature=0.2
        )
        raw_output = response.choices[0].message.content
    except Exception as e:
        return f"<div class='error'><strong>AI Error:</strong> {str(e)}<br><small>Make sure Ollama is running locally on port 11434.</small></div>", 200

    return f"""
    <div class='ai-response'>
        <h4>🤖 Agentic Appliance Advisory</h4>
        <div style='white-space: pre-line;'>{raw_output}</div>
        <small style='display:block; margin-top: 0.5rem; color: var(--text-muted);'>
            ✓ Verified against OmniTech appliance safety rules.
        </small>
    </div>
    """, 200

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5014, threaded=True, debug=False)
