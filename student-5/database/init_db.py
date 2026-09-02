import os
import sqlite3
from datetime import datetime, timedelta

DB_FILE = os.path.join(os.path.dirname(__file__), "warranty.db")
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        product_category TEXT NOT NULL,
        ticket_claim TEXT NOT NULL,
        ticket_status TEXT NOT NULL,
        ticket_created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ai_decision TEXT,
        ai_reasoning TEXT,
        ai_reviewed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        product_category TEXT NOT NULL,
        product_price REAL NOT NULL,
        product_description TEXT NOT NULL,
        product_warranty_years INTEGER NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        order_price REAL NOT NULL,
        order_status TEXT NOT NULL,
        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Delete existing data
    cursor.execute("DELETE FROM tickets")
    cursor.execute("DELETE FROM products")
    cursor.execute("DELETE FROM orders")

    # Seed data for tickets
    ticket_data = [
        (1, 1, 1, "CPU", "The CPU pins were bent upon arrival and opening.", "Pending"),
        (2, 2, 1, "CPU", "The CPU doesn't work.", "Pending"),
        (3, 3, 2, "GPU", "The GPU blew up.", "Pending"),
        (4, 4, 3, "PC Case", "The case came in with the front corner of the case being chipped.", "Pending"),
        (5, 5, 4, "Motherboard", "It doesn't work.", "Pending"),
        (6, 6, 2, "GPU", "The GPU came in chipped, upon use, the GPU was overheating and eventually blew up most likely due to the chip and fans not spinning as fast.", "Pending"),
        (7, 7, 4, "Motherboard", "The motherboard has faulty LED lighting and also visible rust on the metal CPU clipping.", "Pending"),
        (8, 8, 3, "PC Case", "The case looks ugly.", "Pending"),
        (9, 9, 5, "Hard Drive", "Hard drive is faulty and is corrupted, it is unusable.", "Pending"),
        (10, 10, 5, "Hard Drive", "It is slow.", "Pending")
    ]
    cursor.executemany("""
        INSERT INTO tickets (ticket_id, customer_id, product_id, product_category, ticket_claim, ticket_status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ticket_data)

    # Seed data for products
    product_data = [
        (1, "Ryzen 5 3600", "CPU", 200.00, "Ultra fast CPU", 2),
        (2, "Nvidia RTX 5060", "GPU", 400.00, "Ultra fast GPU", 2),
        (3, "DeepCool ATX Case", "PC Case", 50.00, "RGB PC Case", 2),
        (4, "Asus ATX X470 Motherboard", "Motherboard", 150.00, "AMD compatible motherboard", 4),
        (5, "1TB Samsuung HD", "Hard Drive", 75.00, "1TB storage hd", 2)
    ]
    cursor.executemany("""
        INSERT INTO products (product_id, product_name, product_category, product_price, product_description, product_warranty_years)
        VALUES (?, ?, ?, ?, ?, ?)
    """, product_data)

    # Seed data for orders
    order_data = [
        (1, 1, 1, 200.00, "Completed", "2024-9-11 10:43:23"),
        (2, 2, 1, 200.00, "Completed", "2024-9-11 10:43:23"),
        (3, 3, 2, 400.00, "Completed", "2024-9-11 10:43:23"),
        (4, 4, 3, 50.00, "Completed", "2024-9-11 10:43:23"),
        (5, 5, 4, 150.00, "Completed", "2024-9-11 10:43:23"),
        (6, 6, 2, 400.00, "Completed", "2022-9-11 10:43:23"),
        (7, 7, 4, 150.00, "Completed", "2024-9-11 10:43:23"),
        (8, 8, 3, 50.00, "Completed", "2024-9-11 10:43:23"),
        (9, 9, 5, 75.00, "Completed", "2024-9-11 10:43:23"),
        (10, 10, 5, 75.00, "Completed", "2024-9-11 10:43:23")
    ]
    cursor.executemany("""
        INSERT INTO orders (order_id, customer_id, product_id, order_price, order_status, order_date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, order_data)

    conn.commit()
    conn.close()
    print("Database was initialised with 10 tickets, orders and 5 products.")

if __name__ == "__main__":
    init_db()