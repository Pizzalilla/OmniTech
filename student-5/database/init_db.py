import os
import sqlite3
from datetime import datetime, timedelta

DB_FILE = os.path.join(os.path.dirname(__file__), "warranty.db")
# tickets needs id, customer id
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        ticket_id INTEGER PRIMARY KEY AUTO INCREMENT,
        customer_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        product_category TEXT NOT NULL,
        ticket_claim TEXT NOT NULL,
        ticket_status TEXT NOT NULL,
        ticket_created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ai_decision TEXT,
        ai_reasoning TEXT,
        ai_reviewed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        customer_id INTEGER PRIMARY KEY AUTO INCREMENT,
        customer_name TEXT NOT NULL,
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY AUTO INCREMENT,
        product_name TEXT NOT NULL,
        product_category TEXT NOT NULL,
        product_price REAL NOT NULL,
        product_description TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY AUTO INCREMENT,
        customer_id INTEGER NOT NULL,
        order_price REAL NOT NULL,
        order_status TEXT NOT NULL,
        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Delete existing data
    cursor.execute("DELETE FROM tickets")
    cursor.execute("DELETE FROM customers")
    cursor.execute("DELETE FROM products")
    cursor.execute("DELETE FROM orders")

    # Seed Data for tickets
    ticket_data = [
        (1, 1, 1, "CPU", "The CPU pins were bent upon arrival and opening.", "Pending")
        (2, 2, 2, "CPU", "The CPU doesn't work.", "Pending")
        (3, 3, 3, "GPU", "The GPU blew up.", "Pending")
        (4, 4, 4, "PC Case", "The case came in with the front corner of the case being chipped.", "Pending")
        (5, 5, 5, "Motherboard", "It doesn't work.", "Pending")
        (6, 6, 6, "GPU", "The GPU came in chipped, upon use, the GPU was overheating and eventually blew up most likely due to the chip and fans not spinning as fast.", "Pending")
        (7, 7, 7, "Motherboard", "The motherboard has faulty LED lighting and also visible rust on the metal CPU clipping.", "Pending")
        (8, 8, 8, "PC Case", "The case looks ugly.", "Pending")
        (9, 9, 9, "Hard Drive", "Hard drive is faulty and is corrupted, it is unusable.", "Pending")
        (10, 10, 10, "Hard Drive", "It is slow.", "Pending")
    ]
    cursor.executemany("""
        INSERT INTO tickets (ticket_id, customer_id, product_id, product_category, ticket_claim, ticket_status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ticket_data)