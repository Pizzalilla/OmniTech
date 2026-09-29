import copy
import json
import os
import sys
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from markupsafe import escape
import requests

# DATABASE LAYER: the backend reads/writes SQLite directly through database/database.py
DATABASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database")
sys.path.insert(0, DATABASE_DIR)
import database as db
import agent
from mcp_client import McpClient, McpError

app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend",
    static_url_path=""
)
CORS(app)

# DEMO CART: starting items for Customer #101 (restored by "Reload demo cart")
DEMO_CART_ITEMS = [
    {
        "product_id": 511,
        "product_name": "Samsung Fridge 500L",
        "category": "Kitchen",
        "unit_price": 1499.00,
        "quantity": 1,
        "in_stock": True
    },
    {
        "product_id": 512,
        "product_name": "Induction Cooktop 2000W",
        "category": "Kitchen",
        "unit_price": 799.00,
        "quantity": 1,
        "in_stock": True
    },
    {
        "product_id": 513,
        "product_name": "Microwave Oven 1000W",
        "category": "Kitchen",
        "unit_price": 249.00,
        "quantity": 1,
        "in_stock": False
    },
    {
        "product_id": 514,
        "product_name": "Air Fryer 20L",
        "category": "Small Appliances",
        "unit_price": 189.00,
        "quantity": 1,
        "in_stock": True
    }
]

# Active Customer Cart Session State (Customer #101)
CUSTOMER_CART = {
    "user_id": 101,
    "fulfillment": "delivery",
    "delivery_address": "123 Tech Lane, Sydney NSW 2000",
    "delivery_fee": 15.00,
    "items": copy.deepcopy(DEMO_CART_ITEMS)
}


# ---------------------------------------------------------------------------
# HTML HELPERS: build the HTMX fragments the frontend swaps in
# ---------------------------------------------------------------------------

def cart_totals():
    items = CUSTOMER_CART["items"]
    subtotal = sum(i["unit_price"] * i["quantity"] for i in items)
    fee = 0.00 if CUSTOMER_CART["fulfillment"] == "pickup" else CUSTOMER_CART["delivery_fee"]
    return subtotal, fee, subtotal + fee


def render_cart_items_html():
    items = CUSTOMER_CART["items"]
    if not items:
        return """
        <p style='color: var(--text-muted); padding: 1rem;'>Your shopping cart is currently empty.</p>
        <button type="button" class="btn btn-secondary" hx-post="/api/cart/reset" hx-target="#cart-view" hx-swap="innerHTML">
            Reload demo cart
        </button>
        """

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
    subtotal, fee, grand_total = cart_totals()
    gst = subtotal * 0.10

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


def render_order_history_html():
    orders = db.get_all_orders()
    if not orders:
        return "<div class='order-history-list'><p>No orders yet.</p></div>"

    html = "<div class='order-history-list'>"
    for o in reversed(orders):
        options = "".join(
            f"<option value='{s}' {'selected' if s == o['fulfillment_status'] else ''}>{s}</option>"
            for s in db.ORDER_STATUSES
        )
        html += f"""
        <div class="history-item">
            <div>
                <strong>Order #{o['order_id']}</strong> <small>({o['created_at']})</small><br>
                <span>Total: ${o['total_price']:,.2f}</span>
            </div>
            <div class="history-actions">
                <select class="status-select" name="fulfillment_status" title="Update status"
                        hx-put="/api/orders/{o['order_id']}" hx-trigger="change" hx-target="#history-modal-content">
                    {options}
                </select>
                <button type="button" class="btn-remove" title="Delete order"
                        hx-delete="/api/orders/{o['order_id']}" hx-target="#history-modal-content"
                        hx-confirm="Delete order #{o['order_id']}?">🗑</button>
            </div>
        </div>
        """
    html += "</div>"
    return html


def is_htmx():
    return request.headers.get("HX-Request") == "true"


# ---------------------------------------------------------------------------
# PAGE + CART ROUTES (HTMX)
# ---------------------------------------------------------------------------

@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/health")
def health_check():
    return jsonify({"service": "student-4", "status": "healthy", "port": 5004})


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


@app.post("/api/cart/reset")
def reset_cart():
    CUSTOMER_CART["items"] = copy.deepcopy(DEMO_CART_ITEMS)
    return get_cart_view()


# CREATE (checkout): save the cart as a real order in orders.db
@app.post("/api/cart/checkout")
def checkout_order():
    items = CUSTOMER_CART["items"]
    if not items:
        return "<p>Cart is empty.</p>", 200

    _, _, grand_total = cart_totals()
    new_order_id = db.create_order(CUSTOMER_CART["user_id"], grand_total, "Processing", items)
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
    return render_order_history_html()


# ---------------------------------------------------------------------------
# ORDERS REST API (CRUD): JSON for other services, HTML for HTMX requests
# ---------------------------------------------------------------------------

# READ: all orders
@app.get("/api/orders")
def list_orders():
    return jsonify(db.get_all_orders()), 200


# READ: one order with line items
@app.get("/api/orders/<int:order_id>")
def get_order(order_id):
    order = db.get_order(order_id)
    if not order:
        return jsonify({"error": f"Order #{order_id} not found"}), 404
    return jsonify(order), 200


# CREATE: new order from JSON {user_id, fulfillment_status, items: [...]}
@app.post("/api/orders")
def create_order():
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    status = data.get("fulfillment_status", "Pending")

    if "user_id" not in data or not items:
        return jsonify({"error": "user_id and at least one item are required"}), 400
    if status not in db.ORDER_STATUSES:
        return jsonify({"error": f"fulfillment_status must be one of {db.ORDER_STATUSES}"}), 400

    required = ("product_id", "product_name", "category", "quantity", "unit_price")
    if any(k not in i for i in items for k in required):
        return jsonify({"error": f"each item needs {list(required)}"}), 400

    total = data.get("total_price", sum(i["unit_price"] * i["quantity"] for i in items))
    order_id = db.create_order(data["user_id"], total, status, items)
    return jsonify(db.get_order(order_id)), 201


# UPDATE: change fulfilment status
@app.put("/api/orders/<int:order_id>")
def update_order(order_id):
    data = request.get_json(silent=True) or request.form
    status = data.get("fulfillment_status")

    if status not in db.ORDER_STATUSES:
        return jsonify({"error": f"fulfillment_status must be one of {db.ORDER_STATUSES}"}), 400
    if not db.update_order_status(order_id, status):
        return jsonify({"error": f"Order #{order_id} not found"}), 404

    if is_htmx():
        return render_order_history_html()
    return jsonify(db.get_order(order_id)), 200


# DELETE: remove an order and its line items
@app.delete("/api/orders/<int:order_id>")
def delete_order(order_id):
    if not db.delete_order(order_id):
        return jsonify({"error": f"Order #{order_id} not found"}), 404

    if is_htmx():
        return render_order_history_html()
    return jsonify({"deleted": order_id}), 200


# READ: the live cart as JSON (used by the MCP tool get_cart)
@app.get("/api/cart")
def get_live_cart():
    subtotal, fee, total = cart_totals()
    return jsonify({
        "user_id": CUSTOMER_CART["user_id"],
        "fulfillment": CUSTOMER_CART["fulfillment"],
        "delivery_address": CUSTOMER_CART["delivery_address"],
        "items": CUSTOMER_CART["items"],
        "subtotal": round(subtotal, 2),
        "delivery_fee": fee,
        "total": round(total, 2),
    }), 200


# READ: product specs as JSON, e.g. /api/products/specs?ids=511,512 (used by the MCP tool get_product_specs)
@app.get("/api/products/specs")
def get_specs():
    try:
        ids = [int(i) for i in request.args.get("ids", "").split(",") if i.strip()]
    except ValueError:
        return jsonify({"error": "ids must be comma-separated numbers"}), 400
    if not ids:
        return jsonify({"error": "ids is required, e.g. ?ids=511,512"}), 400
    specs = db.get_product_specs(ids)
    return jsonify({"specs": list(specs.values()), "missing": [i for i in ids if i not in specs]}), 200


# READ: a saved shopping cart
@app.get("/api/carts/<int:cart_id>")
def get_cart(cart_id):
    cart = db.get_cart(cart_id)
    if not cart:
        return jsonify({"error": f"Cart #{cart_id} not found"}), 404
    return jsonify(cart), 200


# ---------------------------------------------------------------------------
# AI HELPER: grounded Plan -> Act -> Observe -> Adapt agent (backend/agent.py)
# ---------------------------------------------------------------------------

AI_STATUS = {
    "verified": ("success", "✓ Every number was checked against the product database and store knowledge."),
    "fallback": ("warning", "⚠ The AI used numbers that aren't in our data, so these are the facts straight from the database."),
    "offline": ("error", "<strong>AI Helper Offline:</strong> showing the facts straight from the database. "
                         "Ensure Ollama is running locally on port 11434."),
}
CHECK_ICONS = {"warn": "⚠", "info": "ℹ", "ok": "✓"}


# AI RESULT HTML: answer, safety checks, sources and the agent trace
def render_ai_result_html(result):
    box_class, footnote = AI_STATUS[result["status"]]

    checks = "".join(
        f"<li class='check-{c['level']}'>{CHECK_ICONS[c['level']]} {escape(c['text'])}</li>"
        for c in result["checks"]
    )

    via_mcp = " via MCP" if result.get("specs_source") == "mcp" else ""
    sources = [f"Cart database{via_mcp} ({result['facts_used']} products)"]
    sources += [f"{escape(k['source'])} › {escape(k['heading'])}" for k in result["knowledge"]]

    # RAG STATUS: confidence badge, or why there is no store knowledge
    rag = {
        "ok": f"<span class='rag-badge {escape(result['rag_confidence'] or 'low')}'>RAG confidence: "
              f"{escape(result['rag_confidence'] or 'low')}</span>",
        "insufficient": "<span class='rag-badge none'>📚 I don't have enough information in the store knowledge "
                        "to answer that - only product data was used.</span>",
        "offline": "<span class='rag-badge none'>RAG server offline - only product data was used.</span>",
        "disabled": "<span class='rag-badge none'>RAG disabled - only product data was used.</span>",
    }[result["rag_status"]]

    trace = "".join(f"<li>{escape(t)}</li>" for t in result["trace"])

    return f"""
    <div class='ai-alert-box {box_class}'>
        <div class='ai-output-text'>{escape(result['answer'])}</div>
        <ul class='ai-checks'>{checks}</ul>
        <div class='ai-sources'><strong>Sources:</strong> {' · '.join(sources)}</div>
        <div class='ai-rag'>{rag}</div>
        <small class='ai-footnote'>{footnote}</small>
        <details class='ai-trace'><summary>How the agent worked</summary><ol>{trace}</ol></details>
    </div>
    """


@app.post("/api/orders/ai-validate-cart")
def ai_helper_audit():
    data = request.get_json(silent=True) or request.form
    question = str(data.get("question", "")).strip()
    result = agent.run_cart_agent(question, CUSTOMER_CART["items"])

    if request.is_json:
        return jsonify(result), 200
    return render_ai_result_html(result), 200


# ---------------------------------------------------------------------------
# MCP: order lookup through the shared MCP server's get_order_status tool
# ---------------------------------------------------------------------------

# MCP RESULT HTML: which tool ran, with what inputs, and what came back
def render_mcp_html(tool_name, arguments, box_class, body_html, raw=None):
    raw_html = f"<details class='ai-trace'><summary>Raw MCP result</summary><pre class='mcp-raw'>{escape(raw)}</pre></details>" if raw else ""
    return f"""
    <div class='ai-alert-box {box_class}'>
        <div class='mcp-call'>🧰 <code>{escape(tool_name)}({escape(json.dumps(arguments))})</code></div>
        {body_html}
        {raw_html}
    </div>
    """


@app.post("/api/mcp/order-status")
def mcp_order_status():
    tool_name = "get_order_status"
    try:
        order_id = int(request.form.get("order_id", ""))
    except ValueError:
        return render_mcp_html(tool_name, {}, "error", "<div>Please enter an order number.</div>"), 200
    arguments = {"order_id": order_id}

    if not agent.MCP_ENABLED:
        return render_mcp_html(tool_name, arguments, "error", "<div>MCP is disabled (MCP_ENABLED=false).</div>"), 200

    try:
        res = McpClient(agent.MCP_HOST, timeout=agent.MCP_TIMEOUT).call_tool(tool_name, arguments)
    except McpError as exc:
        return render_mcp_html(tool_name, arguments, "error", f"<div>MCP server rejected the call: {escape(str(exc))}</div>"), 200
    except requests.RequestException:
        return render_mcp_html(tool_name, arguments, "error",
                               f"<div><strong>MCP server offline</strong> at {escape(agent.MCP_HOST)}. "
                               "Start it with <code>python server.py</code> in ai-services/mcp-server.</div>"), 200

    raw = json.dumps(res, indent=2)
    if res["isError"]:
        return render_mcp_html(tool_name, arguments, "warning", f"<div>{escape(res['content'][0]['text'])}</div>", raw), 200

    order = res["structuredContent"]
    items = "".join(f"<li>{i['quantity']}x {escape(i['product_name'])} - ${i['unit_price']:,.2f}</li>" for i in order["items"])
    body = f"""
        <div><strong>Order #{order['order_id']}</strong> - <span class='rag-badge high'>{escape(order['status'])}</span></div>
        <div>Total: ${order['total_price']:,.2f} · {order['item_count']} item(s) · placed {escape(order['created_at'] or '')}</div>
        <ul class='ai-checks'>{items}</ul>
    """
    return render_mcp_html(tool_name, arguments, "success", body, raw), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, threaded=True, debug=False)
