import os
import sqlite3
from pathlib import Path

# student-1/data/catalog.db
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.db"


def get_db_path() -> Path:
    # Docker can override this with DATABASE_PATH
    return Path(os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH)))


def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # rows act like dicts: row["name"]
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
            return None  # no row with that id
    return get_category(category_id)


def delete_category(category_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
        return cursor.rowcount > 0
