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
    })

@app.get("/tickets")
def get_tickets():
    conn = get_db_connection()
    tickets = conn.execute(
        "SELECT * FROM tickets"
    ).fetchall()
    conn.close()
    return jsonify([dict(ticket) for ticket in tickets])

@app.get("/tickets/<int:customer_id>")
def get_tickets_by_customer_id(customer_id):
    conn = get_db_connection()
    ticket = conn.execute(
        "SELECT * FROM tickets where customer_id = ?", (customer_id,),
    ).fetchall()
    conn.close()

    if ticket is None:
        return jsonify({"error", "You have no warranty tickets!"})

    return jsonify([dict(t) for t in ticket])