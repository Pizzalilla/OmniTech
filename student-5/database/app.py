from flask import Flask, jsonify, request
import os
import sqlite3

app = Flask(__name__)

DB_FILE = os.path.join(os.path.dirname(__file__), "warranty.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/")
def health():
    return jsonify({
        "service": "student-5-database",
        "status": "running",
        "port": 5005
    })

@app.get("/tickets")
def get_tickets():
    conn = get_db_connection()
    tickets = conn.execute(
        "SELECT * FROM tickets"
    ).fetchall()
    conn.close()
    return jsonify([dict(ticket) for ticket in tickets])

@app.get("/tickets/customer/<int:customer_id>")
def get_tickets_by_customer_id(customer_id):
    conn = get_db_connection()
    tickets = conn.execute(
        "SELECT * FROM tickets where customer_id = ?", (customer_id,),
    ).fetchall()
    conn.close()

    if tickets is None:
        return jsonify({"error", "You have no warranty tickets!"})

    return jsonify([dict(ticket) for ticket in tickets])

@app.get("/tickets/<int:ticket_id>")
def get_ticket_by_ticket_id(ticket_id):
    conn = get_db_connection()
    ticket = conn.execute(
        "SELECT * FROM tickets where ticket_id = ?", (ticket_id,),
    ).fetchone()
    conn.close()
    if not ticket:
        return jsonify({"error", "Warranty ticket not found"}), 404
    
    return jsonify(dict(ticket))

# @app.post("/tickets/<int:ticket_id>/update")
# def update_ticket(ticket_id):
#     ticket = get_ticket_by_ticket_id(ticket_id)
#     # 
#     conn = get_db_connection()
#     conn.execute("""
#         UPDATE tickets 
#         SET ticket_status = ?, ai_decision = ?, ai_reasoning = ?, ai_reviewed_date = CURRENT_TIMESTAMP
#         WHERE ticket_id = ?
#     """, (the rest to be created ,ticket_id))
#     conn.commit()
#     conn.close()

    # return some message in the ui

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5005, debug=True)