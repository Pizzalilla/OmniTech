import sqlite3
import os
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_FILE = os.path.join(os.path.dirname(__file__), "orders.db")

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/")
def health_check():
    return jsonify({
        "service": "student-4-database",
        "status": "healthy",
        "port": 5014
    })

@app.get("/orders")
def get_orders():
    conn = get_db()
    rows = conn.execute("SELECT * FROM orders ORDER BY order_id ASC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows]), 200

@app.get("/orders/<int:order_id>")
def get_order_by_id(order_id):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        return jsonify({"error": f"Order #{order_id} not found"}), 404
    
    items = conn.execute("SELECT * FROM order_line_items WHERE order_id = ?", (order_id,)).fetchall()
    conn.close()
    
    res = dict(order)
    res["line_items"] = [dict(i) for i in items]
    return jsonify(res), 200

@app.get("/carts/<int:cart_id>")
def get_cart(cart_id):
    conn = get_db()
    cart = conn.execute("SELECT * FROM carts WHERE cart_id = ?", (cart_id,)).fetchone()
    if not cart:
        conn.close()
        return jsonify({"error": f"Cart #{cart_id} not found"}), 404
    
    items = conn.execute("SELECT * FROM order_line_items WHERE cart_id = ?", (cart_id,)).fetchall()
    conn.close()
    
    res = dict(cart)
    res["items"] = [dict(i) for i in items]
    return jsonify(res), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5014, threaded=True, debug=False)
