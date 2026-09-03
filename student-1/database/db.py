import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.db"


def get_db_path() -> Path:
    return Path(os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH)))


def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def list_categories() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, description FROM categories ORDER BY name"
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def get_category(category_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, description FROM categories WHERE id = ?",
            (category_id,),
        ).fetchone()
    return row_to_dict(row)


def create_category(name: str, description: str | None) -> dict:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO categories (name, description) VALUES (?, ?)",
            (name, description),
        )
        conn.commit()
        category_id = cursor.lastrowid
    return get_category(category_id)


def update_category(category_id: int, name: str, description: str | None) -> dict | None:
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE categories SET name = ?, description = ? WHERE id = ?",
            (name, description, category_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
    return get_category(category_id)


def delete_category(category_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
        return cursor.rowcount > 0


PRODUCT_COLUMNS = """
    p.id, p.name, p.brand, p.category_id, c.name AS category_name,
    p.price, p.stock, p.description, p.image_url
"""


def list_products(
    category_id: int | None = None,
    brand: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    search: str | None = None,
    spec_keyword: str | None = None,
) -> list[dict]:
    query = f"""
        SELECT {PRODUCT_COLUMNS}
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE 1=1
    """
    params: list = []

    if category_id is not None:
        query += " AND p.category_id = ?"
        params.append(category_id)
    if brand:
        query += " AND LOWER(p.brand) = LOWER(?)"
        params.append(brand)
    if min_price is not None:
        query += " AND p.price >= ?"
        params.append(min_price)
    if max_price is not None:
        query += " AND p.price <= ?"
        params.append(max_price)
    if search:
        query += " AND (p.name LIKE ? OR p.brand LIKE ? OR p.description LIKE ?)"
        params.extend([f"%{search}%"] * 3)
    if spec_keyword:
        query += """
            AND EXISTS (
                SELECT 1 FROM product_specifications s
                WHERE s.product_id = p.id
                  AND (s.spec_name LIKE ? OR s.spec_value LIKE ?)
            )
        """
        params.extend([f"%{spec_keyword}%"] * 2)

    query += " ORDER BY p.name"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [row_to_dict(row) for row in rows]


def list_brands() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT brand FROM products ORDER BY brand"
        ).fetchall()
    return [row["brand"] for row in rows]


def get_product(product_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT {PRODUCT_COLUMNS}
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE p.id = ?
            """,
            (product_id,),
        ).fetchone()
    return row_to_dict(row)


def create_product(
    name: str,
    brand: str,
    category_id: int,
    price: float,
    stock: int,
    description: str | None,
    image_url: str | None,
) -> dict:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO products
                (name, brand, category_id, price, stock, description, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, brand, category_id, price, stock, description, image_url),
        )
        conn.commit()
        product_id = cursor.lastrowid
    return get_product(product_id)


def update_product(
    product_id: int,
    name: str,
    brand: str,
    category_id: int,
    price: float,
    stock: int,
    description: str | None,
    image_url: str | None,
) -> dict | None:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE products
            SET name = ?, brand = ?, category_id = ?, price = ?,
                stock = ?, description = ?, image_url = ?
            WHERE id = ?
            """,
            (name, brand, category_id, price, stock, description, image_url, product_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
    return get_product(product_id)


def delete_product(product_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        return cursor.rowcount > 0


def list_specifications(product_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, product_id, spec_name, spec_value
            FROM product_specifications
            WHERE product_id = ?
            ORDER BY spec_name
            """,
            (product_id,),
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def get_specification(spec_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, product_id, spec_name, spec_value
            FROM product_specifications
            WHERE id = ?
            """,
            (spec_id,),
        ).fetchone()
    return row_to_dict(row)


def create_specification(product_id: int, spec_name: str, spec_value: str) -> dict:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO product_specifications (product_id, spec_name, spec_value)
            VALUES (?, ?, ?)
            """,
            (product_id, spec_name, spec_value),
        )
        conn.commit()
        spec_id = cursor.lastrowid
    return get_specification(spec_id)


def update_specification(spec_id: int, spec_name: str, spec_value: str) -> dict | None:
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE product_specifications SET spec_name = ?, spec_value = ? WHERE id = ?",
            (spec_name, spec_value, spec_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
    return get_specification(spec_id)


def delete_specification(spec_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM product_specifications WHERE id = ?", (spec_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
