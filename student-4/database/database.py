import os
import sqlite3

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orders.db")

ORDER_STATUSES = ["Pending", "Processing", "Shipped", "Completed", "Cancelled"]


_specs_ready = False


# CONNECTION: open orders.db (create + seed it first if it is missing)
def get_db():
    global _specs_ready
    if not os.path.exists(DB_FILE):
        from init_db import init_database
        init_database()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # UPGRADE: older orders.db files have no product_specs table yet
    if not _specs_ready:
        from init_db import create_product_specs
        create_product_specs(conn.cursor())
        conn.commit()
        _specs_ready = True
    return conn


# READ: all orders, newest last
def get_all_orders():
    conn = get_db()
    rows = conn.execute("SELECT * FROM orders ORDER BY order_id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# READ: one order with its line items (None if not found)
def get_order(order_id):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        return None
    items = conn.execute("SELECT * FROM order_line_items WHERE order_id = ?", (order_id,)).fetchall()
    conn.close()
    result = dict(order)
    result["line_items"] = [dict(i) for i in items]
    return result


# CREATE: save a new order and its line items, return the new order_id
def create_order(user_id, total_price, fulfillment_status, items):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO orders (user_id, total_price, fulfillment_status) VALUES (?, ?, ?)",
        (user_id, total_price, fulfillment_status)
    )
    order_id = cursor.lastrowid
    conn.executemany(
        """
        INSERT INTO order_line_items (order_id, cart_id, product_id, product_name, category, quantity, unit_price)
        VALUES (?, NULL, ?, ?, ?, ?, ?)
        """,
        [(order_id, i["product_id"], i["product_name"], i["category"], i["quantity"], i["unit_price"]) for i in items]
    )
    conn.commit()
    conn.close()
    return order_id


# UPDATE: change an order's fulfilment status (False if order not found)
def update_order_status(order_id, fulfillment_status):
    conn = get_db()
    cursor = conn.execute(
        "UPDATE orders SET fulfillment_status = ? WHERE order_id = ?",
        (fulfillment_status, order_id)
    )
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


# DELETE: remove an order and its line items (False if order not found)
def delete_order(order_id):
    conn = get_db()
    conn.execute("DELETE FROM order_line_items WHERE order_id = ?", (order_id,))
    cursor = conn.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


# READ: product specs for the given product ids, as {product_id: {...}}
def get_product_specs(product_ids):
    ids = list(product_ids)
    if not ids:
        return {}
    conn = get_db()
    marks = ",".join("?" for _ in ids)
    rows = conn.execute(f"SELECT * FROM product_specs WHERE product_id IN ({marks})", ids).fetchall()
    conn.close()
    return {r["product_id"]: dict(r) for r in rows}


# READ: one saved shopping cart with its items (None if not found)
def get_cart(cart_id):
    conn = get_db()
    cart = conn.execute("SELECT * FROM carts WHERE cart_id = ?", (cart_id,)).fetchone()
    if not cart:
        conn.close()
        return None
    items = conn.execute("SELECT * FROM order_line_items WHERE cart_id = ?", (cart_id,)).fetchall()
    conn.close()
    result = dict(cart)
    result["items"] = [dict(i) for i in items]
    return result
