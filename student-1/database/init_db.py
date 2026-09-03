# Create tables and insert starter rows if the database is empty.

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

        # don't re-seed on every restart
        existing = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if existing > 0:
            return

        categories = [
            ("Refrigerators", "Cooling appliances for food storage"),
            ("Washing Machines", "Laundry and garment care"),
            ("Air Conditioners", "Climate control and cooling units"),
            ("Dishwashers", "Automatic kitchen dishwashing"),
            ("Ovens & Cooktops", "Baking, roasting, and stovetop cooking"),
            ("Microwaves", "Fast reheating and defrosting"),
            ("Vacuum Cleaners", "Floor care and robotic cleaning"),
            ("Air Purifiers", "Air filtration and allergen removal"),
            ("Coffee Machines", "Espresso and filter coffee brewing"),
            ("Water Heaters", "Hot water systems for the home"),
        ]
        conn.executemany(
            "INSERT INTO categories (name, description) VALUES (?, ?)",
            categories,
        )

        # category_id follows the insert order above
        products = [
            (
                "FreshKeep XL 520",
                "FreshKeep",
                1,
                1299.00,
                8,
                "French-door refrigerator with smart temperature zones.",
                "https://placehold.co/400x300?text=Fridge",
            ),
            (
                "FreshKeep Mini Bar 120",
                "FreshKeep",
                1,
                449.00,
                21,
                "Compact bar fridge for studies and small kitchens.",
                "https://placehold.co/400x300?text=Bar+Fridge",
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
            (
                "SpinMaster Duo Dryer 9",
                "SpinMaster",
                2,
                1150.00,
                4,
                "Heat pump dryer that pairs with the Pro 10 washer.",
                "https://placehold.co/400x300?text=Dryer",
            ),
            (
                "CoolBreeze 5000 Split",
                "CoolBreeze",
                3,
                899.99,
                12,
                "Energy-efficient split-system air conditioner for medium rooms.",
                "https://placehold.co/400x300?text=Split+AC",
            ),
            (
                "CoolBreeze Portable 9",
                "CoolBreeze",
                3,
                549.00,
                0,
                "Wheeled portable air conditioner for rooms without a split unit.",
                "https://placehold.co/400x300?text=Portable+AC",
            ),
            (
                "AquaJet Slimline 14",
                "AquaJet",
                4,
                899.00,
                6,
                "Slimline dishwasher with 14 place settings and a quiet night cycle.",
                "https://placehold.co/400x300?text=Dishwasher",
            ),
            (
                "HeatWave Pyrolytic 90",
                "HeatWave",
                5,
                1799.00,
                3,
                "Wide pyrolytic oven with self-cleaning and steam assist.",
                "https://placehold.co/400x300?text=Oven",
            ),
            (
                "QuickChef Inverter 32",
                "QuickChef",
                6,
                329.00,
                18,
                "Inverter microwave with even reheating and grill function.",
                "https://placehold.co/400x300?text=Microwave",
            ),
            (
                "DustDevil Robot S2",
                "DustDevil",
                7,
                999.00,
                9,
                "Robot vacuum with self-emptying dock and mopping pad.",
                "https://placehold.co/400x300?text=Robot+Vacuum",
            ),
            (
                "PureAir Tower 400",
                "PureAir",
                8,
                649.00,
                11,
                "HEPA tower purifier rated for open-plan living areas.",
                "https://placehold.co/400x300?text=Air+Purifier",
            ),
            (
                "BaristaOne Automatic",
                "BaristaOne",
                9,
                1249.00,
                5,
                "Bean-to-cup espresso machine with automatic milk texturing.",
                "https://placehold.co/400x300?text=Coffee+Machine",
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

        specs = [
            (1, "Capacity", "520 L"),
            (1, "Energy Rating", "5 stars"),
            (1, "Dimensions", "180 x 90 x 75 cm"),
            (2, "Capacity", "120 L"),
            (2, "Energy Rating", "3 stars"),
            (2, "Noise Level", "38 dB"),
            (3, "Capacity", "10 kg"),
            (3, "Spin Speed", "1400 RPM"),
            (3, "Water Usage", "45 L per cycle"),
            (4, "Capacity", "9 kg"),
            (4, "Dryer Type", "Heat pump"),
            (4, "Energy Rating", "4 stars"),
            (5, "Cooling Capacity", "12000 BTU"),
            (5, "Energy Rating", "4 stars"),
            (5, "Noise Level", "42 dB"),
            (6, "Cooling Capacity", "9000 BTU"),
            (6, "Coverage", "25 sqm"),
            (6, "Noise Level", "48 dB"),
            (7, "Place Settings", "14"),
            (7, "Water Usage", "9.5 L per cycle"),
            (7, "Noise Level", "44 dB"),
            (8, "Oven Capacity", "105 L"),
            (8, "Cleaning", "Pyrolytic"),
            (8, "Energy Rating", "4 stars"),
            (9, "Capacity", "32 L"),
            (9, "Power", "1000 W"),
            (9, "Functions", "Reheat, defrost, grill"),
            (10, "Runtime", "180 min"),
            (10, "Suction", "5000 Pa"),
            (10, "Dustbin", "Self-emptying dock"),
            (11, "Coverage", "60 sqm"),
            (11, "Filter", "HEPA H13"),
            (11, "Noise Level", "24 dB"),
            (12, "Water Tank", "1.8 L"),
            (12, "Pump Pressure", "19 bar"),
            (12, "Grinder", "Ceramic burr"),
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
