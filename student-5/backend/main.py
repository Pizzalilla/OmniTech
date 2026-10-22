import os
import sys

STUDENT5_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STUDENT5_DIR)

import requests
from flask import Flask, render_template, jsonify, send_from_directory, request
from database.app import get_db_connection
from database.init_db import init_db

from agent import run_agentic_evaluation
import rag_client
from mcp_client import McpClient

RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() == "true"
MCP_ENABLED = os.getenv("MCP_ENABLED", "true").lower() == "true"
MCP_HOST = os.getenv("MCP_HOST", "http://localhost:6003")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "frontend", "templates"),
    static_folder=os.path.join(BASE_DIR, "frontend", "css")
)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/tickets")
def tickets():
    conn = get_db_connection()
    tickets = conn.execute(
        "SELECT * FROM tickets ORDER BY ticket_id"
    ).fetchall()
    conn.close()

    return render_template(
        "ai_tickets.html",
        tickets=tickets
    )

@app.route("/create-ticket")
def create_ticket_page():
    conn = get_db_connection()
    orders = conn.execute("""
        SELECT
            orders.order_id,
            orders.customer_id,
            orders.product_id,
            orders.order_price,
            orders.order_status,
            orders.order_date,
            products.product_name,
            products.product_category
        FROM orders
        JOIN products
            ON orders.product_id = products.product_id
        ORDER BY orders.order_id
    """).fetchall()
    conn.close()

    return render_template(
        "ticket_creation.html",
        orders=orders
    )

@app.route("/ai-evaluation")
def ai_evaluation():
    conn = get_db_connection()
    tickets = conn.execute(
        "SELECT * FROM tickets ORDER BY ticket_id"
    ).fetchall()
    conn.close()

    return render_template("index.html", tickets=tickets)

@app.post("/api/tickets/<int:ticket_id>/evaluate")
def ai_evaluate_ticket(ticket_id):
    try:
        conn = get_db_connection()
        ticket = conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?",
            (ticket_id,)
        ).fetchone()
        conn.close()
        if ticket is None:
            return jsonify({
                "success": False,
                "error": f"Ticket {ticket_id} not found."
            }), 404
        result = run_agentic_evaluation(ticket)

        if not result["success"]:
            if result.get("failure_type") == "verification_failed":
                return jsonify(result), 200

            return jsonify(result), 500

        return jsonify({
            "success": True,
            "ticket_id": ticket["ticket_id"],
            "decision": result["decision"],
            "reasoning": result["reasoning"],
            "review": result["review"],
            "attempts": result["attempts"]
        }), 200

    except Exception as exc:
        print(
            f"AI evaluation failed for ticket {ticket_id}: {exc}"
        )
        return jsonify({
            "success": False,
            "error": "Evaluation request failed."
        }), 503

@app.post("/tickets/<int:ticket_id>/update")
def update_ticket(ticket_id):    
    data = request.get_json()
    decision = data.get("decision")
    reasoning = data.get("reasoning")
    if not decision or not reasoning:
        return jsonify({
            "success": False,
            "error": "AI decision and reasoning are required."
        }), 400

    ticket_status = decision
    conn = get_db_connection()
    conn.execute("""
        UPDATE tickets
        SET ticket_status = ?,
            ai_decision = ?,
            ai_reasoning = ?,
            ai_reviewed_date = CURRENT_TIMESTAMP
        WHERE ticket_id = ?
    """, (ticket_status, decision, reasoning, ticket_id)
    )
    conn.commit()
    conn.close()
    return jsonify({
        "success": True,
        "message": f"Ticket {ticket_id} updated successfully."
    }), 200

@app.post("/tickets/create")
def create_ticket():
    data = request.get_json()
    order_id = data.get("order_id")
    ticket_claim = data.get("ticket_claim")
    if not order_id or not ticket_claim:
        return jsonify({
            "success": False,
            "error": "Order ID and warranty claim are required."
        }), 400

    conn = get_db_connection()
    order = conn.execute("""
        SELECT customer_id, product_id
        FROM orders
        WHERE order_id = ?
    """, (order_id,)).fetchone()
    if order is None:
        conn.close()

        return jsonify({
            "success": False,
            "error": "Order not found."
        }), 404

    product = conn.execute("""
        SELECT product_category
        FROM products
        WHERE product_id = ?
    """, (order["product_id"],)).fetchone()
    if product is None:
        conn.close()

        return jsonify({
            "success": False,
            "error": "Product not found."
        }), 404

    conn.execute("""
        INSERT INTO tickets (
            customer_id,
            product_id,
            product_category,
            ticket_claim,
            ticket_status
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        order["customer_id"],
        order["product_id"],
        product["product_category"],
        ticket_claim,
        "Pending"
    ))
    conn.commit()
    conn.close()
    return jsonify({
        "success": True,
        "message": "Warranty ticket created successfully."
    }), 201

@app.delete("/tickets/<int:ticket_id>/delete")
def delete_ticket(ticket_id):
    conn = get_db_connection()
    ticket = conn.execute("""
        SELECT ticket_status
        FROM tickets
        WHERE ticket_id = ?
    """, (ticket_id,)).fetchone()
    if ticket is None:
        conn.close()
        return jsonify({
            "success": False,
            "error": "Warranty ticket not found."
        }), 404

    conn.execute("""
        DELETE FROM tickets
        WHERE ticket_id = ?
    """, (ticket_id,))
    conn.commit()
    conn.close()
    return jsonify({
        "success": True,
        "message": f"Ticket {ticket_id} removed successfully."
    }), 200

@app.get("/api/products/<int:product_id>")
def get_product(product_id):
    conn = get_db_connection()
    product = conn.execute("""
        SELECT
            product_id,
            product_name,
            product_category,
            product_price,
            product_description,
            product_warranty_years
        FROM products
        WHERE product_id = ?
    """, (product_id,)).fetchone()
    conn.close()
    if product is None:
        return jsonify({
            "success": False,
            "error": "Product not found."
        }), 404

    return jsonify({
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "product_category": product["product_category"],
        "product_price": product["product_price"],
        "product_description": product["product_description"],
        "product_warranty_years": product["product_warranty_years"]
    })

# RAG Implementation
@app.post("/api/rag/warranty")
def rag_warranty():
    data = request.get_json(silent=True) or {}

    order_id = data.get("order_id")
    ticket_claim = (data.get("ticket_claim") or "").strip()

    if not order_id or not ticket_claim:
        return jsonify({
            "success": False,
            "error": "Order ID and warranty claim are required."
        }), 400

    conn = get_db_connection()

    order = conn.execute("""
        SELECT products.product_category
        FROM orders
        JOIN products
            ON orders.product_id = products.product_id
        WHERE orders.order_id = ?
    """, (order_id,)).fetchone()

    conn.close()

    if order is None:
        return jsonify({
            "success": False,
            "error": "Order not found."
        }), 404

    product_category = order["product_category"]

    query = (
        f"I want to submit a warranty claim for a "
        f"{product_category}. My current claim is: "
        f"\"{ticket_claim}\". "
        f"What additional information should I include "
        f"so that the claim contains enough information "
        f"for warranty assessment?"
    )

    if not RAG_ENABLED:
        return jsonify({
            "success": False,
            "error": "RAG integration is disabled in this environment."
        }), 503

    try:
        result = rag_client.ask(query)

        return jsonify({
            "success": True,
            "result": result
        })

    except requests.RequestException:
        return jsonify({
            "success": False,
            "error": "The shared RAG server is not reachable right now."
        }), 503

# MCP Implementation
@app.get("/api/tickets/<int:ticket_id>/product-info")
def get_ticket_product_info(ticket_id):
    conn = get_db_connection()
    ticket = conn.execute("""
        SELECT ticket_id, product_id, product_category, ticket_claim
        FROM tickets
        WHERE ticket_id = ?
    """, (ticket_id,)).fetchone()
    conn.close()
    if ticket is None:
        return jsonify({
            "success": False,
            "error": "Ticket not found."
        }), 404

    if not MCP_ENABLED:
            return jsonify({
                "success": False,
                "error": "MCP integration is disabled in this environment."
            }), 503

    try:
        mcp = McpClient(MCP_HOST)
        mcp.initialize()
        result = mcp.call_tool(
            "get_warranty_product",
            {
                "product_id": ticket["product_id"]
            }
        )
        return jsonify({
            "success": True,
            "ticket_id": ticket["ticket_id"],
            "result": result
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"MCP product information request failed: {str(e)}"
        }), 503

@app.route("/shared/css/<path:filename>")
def shared_css(filename):
    return send_from_directory(
        os.path.join(
            os.path.dirname(BASE_DIR),
            "shared",
            "frontend",
            "css"
        ),
        filename
    )

with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
