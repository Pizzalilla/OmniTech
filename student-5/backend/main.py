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
import multi_agent_client

RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() == "true"
MCP_ENABLED = os.getenv("MCP_ENABLED", "true").lower() == "true"
MCP_HOST = os.getenv("MCP_HOST", "http://localhost:6003")

MULTI_AGENT_ENABLED = (os.getenv("MULTI_AGENT_ENABLED", "true").lower() == "true")
MULTI_AGENT_STUDENT_ID = os.getenv("STUDENT_ID", "student-5")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "frontend", "templates"),
    static_folder=os.path.join(BASE_DIR, "frontend", "css")
)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

def ensure_multi_agent_review_table():
    """Store the link between each warranty ticket and its workflows."""
    conn = get_db_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ticket_multi_agent_reviews (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                workflow_id TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'running',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticket_multi_agent_reviews_ticket
            ON ticket_multi_agent_reviews(ticket_id, review_id DESC)
        """)
        conn.commit()
    finally:
        conn.close()

def _ticket_product_from_mcp(product_id):
    """Retrieve product evidence using the existing MCP tool."""
    if not MCP_ENABLED:
        raise RuntimeError("MCP integration is disabled.")

    mcp = McpClient(MCP_HOST)
    mcp.initialize()
    result = mcp.call_tool(
        "get_warranty_product",
        {"product_id": product_id}
    )
    if isinstance(result, dict):
        product = result.get("structuredContent", result)
    else:
        product = None

    if not isinstance(product, dict) or not product:
        raise RuntimeError(
            "MCP returned no structured product information."
        )
    return product

def _workflow_from_server_response(data):
    """Support either a direct workflow or a wrapped workflow response."""
    if isinstance(data, dict) and isinstance(data.get("workflow"), dict):
        return data["workflow"]

    return data if isinstance(data, dict) else {}

def _save_linked_workflow_status(workflow_id, status):
    if not workflow_id or not status:
        return

    conn = get_db_connection()
    try:
        conn.execute("""
            UPDATE ticket_multi_agent_reviews
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE workflow_id = ?
        """, (status, workflow_id))
        conn.commit()
    finally:
        conn.close()

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

@app.post("/api/tickets/<int:ticket_id>/multi-agent-reviews")
def start_ticket_multi_agent_review(ticket_id):
    if not MULTI_AGENT_ENABLED:
        return jsonify({
            "success": False,
            "error": "Multi-Agent review is disabled."
        }), 503

    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?",
            (ticket_id,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return jsonify({
            "success": False,
            "error": f"Ticket {ticket_id} not found."
        }), 404

    ticket = dict(row)
    print("[Multi-Agent] Retrieving product information through MCP...")
    try:
        product_info = _ticket_product_from_mcp(ticket["product_id"])
    except Exception as exc:
        app.logger.exception("MCP retrieval failed before Multi-Agent review")
        return jsonify({
            "success": False,
            "error": "Could not retrieve product information through MCP.",
            "detail": str(exc)
        }), 503

    evidence = {
        "warranty_ticket": {
            "ticket_id": ticket.get("ticket_id"),
            "product_id": ticket.get("product_id"),
            "product_category": ticket.get("product_category"),
            "claim": ticket.get("ticket_claim"),
            "current_ticket_status": ticket.get("ticket_status"),
        },
        "product_information_from_mcp": product_info,
    }
    if ticket.get("ai_decision") or ticket.get("ai_reasoning"):
        evidence["previous_ai_evaluation"] = {
            "decision": ticket.get("ai_decision"),
            "reasoning": ticket.get("ai_reasoning"),
            "reviewed_date": ticket.get("ai_reviewed_date"),
        }

    task = (
        "Review this warranty claim as a separate quality-review workflow. "
        "Use only the supplied ticket and MCP product evidence. Assess "
        "whether the claim is consistent with the product information, "
        "identify missing evidence and risks, and state what should be "
        "checked before a warranty decision is made. Do not invent "
        "warranty terms. Do not update the ticket or automatically "
        "approve or reject the warranty claim. The workflow ends with "
        "a human review of its output."
    )
    print(
        f"[Multi-Agent] Starting workflow for ticket {ticket_id}; "
        f"student={MULTI_AGENT_STUDENT_ID}"
    )
    print(
        f"[Multi-Agent] Server URL: "
        f"{multi_agent_client.MULTI_AGENT_HOST}"
    )
    try:
        workflow = multi_agent_client.start(
            task=task,
            evidence=evidence,
            student=MULTI_AGENT_STUDENT_ID,
        )
    except requests.RequestException as exc:
        app.logger.exception("Could not connect to Multi-Agent Server")
        return jsonify({
            "success": False,
            "error": "The shared Multi-Agent Server could not be reached.",
            "detail": str(exc),
        }), 503
    except multi_agent_client.MultiAgentError as exc:
        app.logger.exception("Multi-Agent Server rejected the request")
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 502

    workflow = _workflow_from_server_response(workflow)
    workflow_id = workflow.get("id")
    if not workflow_id:
        return jsonify({
            "success": False,
            "error": "The Multi-Agent Server did not return a workflow ID.",
            "detail": workflow,
        }), 502

    status = workflow.get("status", "unknown")
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO ticket_multi_agent_reviews
                (ticket_id, workflow_id, status)
            VALUES (?, ?, ?)
        """, (ticket_id, workflow_id, status))
        conn.commit()
    finally:
        conn.close()

    return jsonify({
        "success": True,
        "ticket_id": ticket_id,
        "workflow_id": workflow_id,
        "status": status,
        "workflow": workflow,
    }), 201

@app.get("/api/tickets/<int:ticket_id>/multi-agent-reviews")
def list_ticket_multi_agent_reviews(ticket_id):
    conn = get_db_connection()
    try:
        ticket = conn.execute(
            "SELECT ticket_id FROM tickets WHERE ticket_id = ?",
            (ticket_id,)
        ).fetchone()
        if ticket is None:
            return jsonify({
                "success": False,
                "error": "Warranty ticket not found."
            }), 404

        rows = conn.execute("""
            SELECT workflow_id, status, created_at, updated_at
            FROM ticket_multi_agent_reviews
            WHERE ticket_id = ?
            ORDER BY review_id DESC
        """, (ticket_id,)).fetchall()
    finally:
        conn.close()

    reviews = []
    for item in rows:
        workflow_id = item["workflow_id"]
        status = item["status"]
        workflow = None
        workflow_error = None
        try:
            response_data = multi_agent_client.get(workflow_id)
            workflow = _workflow_from_server_response(response_data)
            status = workflow.get("status", status)
            _save_linked_workflow_status(workflow_id, status)
        except (requests.RequestException,
                multi_agent_client.MultiAgentError,
                ValueError) as exc:
            workflow_error = (
                f"Could not refresh the workflow from the server: {exc}"
            )
        reviews.append({
            "workflow_id": workflow_id,
            "status": status,
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
            "workflow": workflow,
            "workflow_error": workflow_error,
        })
    return jsonify({
        "success": True,
        "ticket_id": ticket_id,
        "reviews": reviews,
    }), 200

@app.post(
    "/api/tickets/<int:ticket_id>/multi-agent-reviews/"
    "<workflow_id>/decision"
)
def decide_ticket_multi_agent_review(ticket_id, workflow_id):
    if not MULTI_AGENT_ENABLED:
        return jsonify({
            "success": False,
            "error": "Multi-Agent review is disabled."
        }), 503

    data = request.get_json(silent=True) or {}
    decision = (data.get("decision") or "").strip()
    reviewer = (data.get("reviewer") or "staff").strip()
    note = (data.get("note") or "").strip()
    corrected_answer = (data.get("corrected_answer") or "").strip()
    conn = get_db_connection()
    try:
        linked_review = conn.execute("""
            SELECT workflow_id
            FROM ticket_multi_agent_reviews
            WHERE ticket_id = ? AND workflow_id = ?
        """, (ticket_id, workflow_id)).fetchone()
    finally:
        conn.close()

    if linked_review is None:
        return jsonify({
            "success": False,
            "error": "This workflow is not linked to this ticket."
        }), 404

    try:
        response_data = multi_agent_client.decide(
            workflow_id=workflow_id,
            decision=decision,
            reviewer=reviewer,
            note=note,
            corrected_answer=corrected_answer,
        )
        workflow = _workflow_from_server_response(response_data)
        status = workflow.get("status")
        if status:
            _save_linked_workflow_status(workflow_id, status)
        return jsonify({
            "success": True,
            "ticket_id": ticket_id,
            "workflow_id": workflow_id,
            "workflow": workflow,
            "response": response_data,
        }), 200

    except multi_agent_client.MultiAgentError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 400

    except requests.RequestException as exc:
        return jsonify({
            "success": False,
            "error": "The Multi-Agent Server could not be reached.",
            "detail": str(exc),
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
    ensure_multi_agent_review_table()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
