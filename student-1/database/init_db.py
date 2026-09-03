"""Create tables and insert starter rows if the database is empty."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.db import get_connection, get_db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    brand TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    price REAL NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    image_url TEXT,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS product_specifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    spec_name TEXT NOT NULL,
    spec_value TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);
"""


def init_db(seed: bool = True) -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)

        if not seed:
            return

        # only seed once — skip if categories already exist
        existing = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if existing > 0:
            return

        categories = [
            ("Refrigerators", "Cooling appliances for food storage"),
            ("Washing Machines", "Laundry and garment care"),
            ("Air Conditioners", "Climate control units"),
        ]
        conn.executemany(
            "INSERT INTO categories (name, description) VALUES (?, ?)",
            categories,
        )

        # category_id: 1=Refrigerators, 2=Washing Machines, 3=Air Conditioners
        products = [
            (
                "CoolBreeze 5000",
                "CoolBreeze",
                3,
                899.99,
                12,
                "Energy-efficient split-system air conditioner for medium rooms.",
                "https://placehold.co/400x300?text=AC",
            ),
            (
                "FreshKeep XL",
                "FreshKeep",
                1,
                1299.00,
                8,
                "French-door refrigerator with smart temperature zones.",
                "https://placehold.co/400x300?text=Fridge",
            ),
            (
                "SpinMaster Pro 10",
                "SpinMaster",
                2,
                749.50,
                15,
                "Front-load washer with 10 kg capacity and quick-wash cycle.",
                "https://placehold.co/400x300?text=Washer",
            ),
        ]
        conn.executemany(
            """
            INSERT INTO products
                (name, brand, category_id, price, stock, description, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            products,
        )

        # (product_id, spec_name, spec_value)
        specs = [
            (1, "Cooling Capacity", "12000 BTU"),
            (1, "Energy Rating", "4 stars"),
            (1, "Noise Level", "42 dB"),
            (2, "Capacity", "520 L"),
            (2, "Energy Rating", "5 stars"),
            (2, "Dimensions", "180 x 90 x 75 cm"),
            (3, "Capacity", "10 kg"),
            (3, "Spin Speed", "1400 RPM"),
            (3, "Water Usage", "45 L per cycle"),
        ]
        conn.executemany(
            """
            INSERT INTO product_specifications (product_id, spec_name, spec_value)
            VALUES (?, ?, ?)
            """,
            specs,
        )

        conn.commit()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {get_db_path()}")
