import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(__file__), "orders.db")

def init_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS carts (
        cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        total_price REAL NOT NULL,
        fulfillment_status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_line_items (
        line_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        cart_id INTEGER,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (order_id),
        FOREIGN KEY (cart_id) REFERENCES carts (cart_id)
    )
    """)

    # Clean existing data
    cursor.execute("DELETE FROM order_line_items")
    cursor.execute("DELETE FROM orders")
    cursor.execute("DELETE FROM carts")

    # Seed 10 Orders with Home Appliances
    orders_data = [
        (1, 101, 2199.00, "Completed"),
        (2, 102, 1450.00, "Processing"),
        (3, 103, 899.00,  "Shipped"),
        (4, 104, 249.99,  "Completed"),
        (5, 105, 1299.50, "Processing"),
        (6, 106, 680.00,  "Pending"),
        (7, 107, 3450.00, "Shipped"),
        (8, 108, 180.00,  "Cancelled"),
        (9, 109, 950.00,  "Completed"),
        (10, 110, 420.00, "Pending")
    ]
    cursor.executemany("INSERT INTO orders (order_id, user_id, total_price, fulfillment_status) VALUES (?, ?, ?, ?)", orders_data)

    # Seed Line Items
    line_items_data = [
        (1, None, 501, "French Door Smart Refrigerator 600L", "Kitchen", 1, 2199.00),
        (2, None, 502, "Front Load Washer & Heat Pump Dryer", "Laundry", 1, 1450.00),
        (3, None, 503, "Robotic Vacuum & Sonic Mop Station", "Cleaning", 1, 899.00),
        (4, None, 504, "Smart Convection Air Fryer Oven 12L", "Small Kitchen", 1, 249.99),
        (5, None, 505, "Built-in Induction Cooktop 4-Zone", "Kitchen", 1, 1299.50),
        (6, None, 506, "Ultra-Quiet Smart Dishwasher", "Kitchen", 1, 680.00),
        (7, None, 507, "Multi-Split Inverter Air Conditioner", "Climate Control", 1, 3450.00),
        (8, None, 508, "Cold-Press Slow Juicer Extractor", "Small Kitchen", 1, 180.00),
        (9, None, 509, "Smart Espresso Machine & Grinder", "Small Kitchen", 1, 950.00),
        (10, None, 510, "HEPA Air Purifier & Humidifier", "Climate Control", 1, 420.00)
    ]
    cursor.executemany("""
    INSERT INTO order_line_items (order_id, cart_id, product_id, product_name, category, quantity, unit_price)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, line_items_data)

    # Seed 2 Active Shopping Carts
    cursor.execute("INSERT INTO carts (cart_id, user_id) VALUES (1, 201)")
    cursor.execute("INSERT INTO carts (cart_id, user_id) VALUES (2, 202)")

    cart_items = [
        (None, 1, 501, "French Door Smart Refrigerator 600L", "Kitchen", 1, 2199.00),
        (None, 1, 601, "Refrigerator Water Filter Replacement", "Accessories", 2, 45.00),
        (None, 2, 504, "Smart Convection Air Fryer Oven 12L", "Small Kitchen", 1, 249.99)
    ]
    cursor.executemany("""
    INSERT INTO order_line_items (order_id, cart_id, product_id, product_name, category, quantity, unit_price)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, cart_items)

    conn.commit()
    conn.close()
    print("SUCCESS: Database orders.db initialized with 10 orders and active carts.")

if __name__ == "__main__":
    init_database()
