"""
Database layer for Customer Profiles & Preferences microservice.
Exclusive owner of Customers, Preferences, and PreferenceTags tables.
"""
import os
import sqlite3

DB_PATH = os.getenv(
    "DB_PATH", os.path.join(os.path.dirname(__file__), "users.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS Customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    shipping_street TEXT NOT NULL DEFAULT '',
    shipping_city TEXT NOT NULL DEFAULT '',
    shipping_state TEXT NOT NULL DEFAULT '',
    shipping_postcode TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    ecosystem TEXT NOT NULL,
    budget_tier TEXT NOT NULL DEFAULT 'mid-range',
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES Customers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS PreferenceTags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    tag_name TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'user' CHECK (source IN ('user', 'ai_agent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES Customers(id) ON DELETE CASCADE,
    UNIQUE(customer_id, tag_name)
);

CREATE INDEX IF NOT EXISTS idx_preferences_customer ON Preferences(customer_id);
CREATE INDEX IF NOT EXISTS idx_tags_customer ON PreferenceTags(customer_id);
"""

SYSTEM_CATEGORIES = {
    "apple-ecosystem", "android-ecosystem", "windows-ecosystem", "linux-user",
    "smart-home-user", "audiophile", "4k-video-editing", "pc-gaming",
    "mobile-gaming", "budget-conscious", "premium-tech", "remote-worker",
    "fitness-tracking", "portable-audio", "photographer"
}

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn

def init_db():
    get_db().close()

def seed_db():
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM Customers").fetchone()[0] > 0:
        conn.close()
        return

    customers = [
        ("Alex", "Mercer", "alex.mercer@example.com", "0412345678", "100 Market St", "Sydney", "NSW", "2000"),
        ("Sarah", "Connor", "sarah.c@example.com", "0423456789", "42 Wallaby Way", "Sydney", "NSW", "2000"),
        ("David", "Kim", "dkim@example.com", "0434567890", "12 High St", "Melbourne", "VIC", "3000"),
        ("Emma", "Watson", "emma.w@example.com", "0445678901", "88 Queen St", "Brisbane", "QLD", "4000"),
        ("Liam", "Neeson", "liam.n@example.com", "0456789012", "55 George St", "Perth", "WA", "6000"),
        ("Olivia", "Rodeo", "olivia.r@example.com", "0467890123", "99 King St", "Adelaide", "SA", "5000"),
        ("Noah", "Cent", "noah.c@example.com", "0478901234", "14 Park Rd", "Hobart", "TAS", "7000"),
        ("Mia", "Theresa", "mia.t@example.com", "0489012345", "77 Ocean Ave", "Gold Coast", "QLD", "4217"),
        ("Ethan", "Hunt", "ethan.h@example.com", "0490123456", "303 Mission Rd", "Canberra", "ACT", "2600"),
        ("Sophia", "Loren", "sophia.l@example.com", "0401234567", "123 Sunset Blvd", "Newcastle", "NSW", "2300")
    ]
    for fn, ln, em, ph, st, ct, sta, pc in customers:
        conn.execute(
            "INSERT INTO Customers (first_name, last_name, email, phone, shipping_street, shipping_city, shipping_state, shipping_postcode) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (fn, ln, em, ph, st, ct, sta, pc)
        )

    preferences = [
        (1, "Apple", "premium", "Focuses on high-end creative setups and 4K media work."),
        (2, "Android/Google", "budget", "Looks for durable hardware and high battery capacity."),
        (3, "Windows", "mid-range", "Uses setup for PC gaming and general multitasking."),
        (4, "Apple", "mid-range", "Prefers portable mobile devices for study and reading."),
        (5, "Smart Home", "premium", "Automating home lights, audio, and high security cameras."),
        (6, "Linux", "budget", "Developer looking for open hardware and high performance storage."),
        (7, "Windows", "premium", "Heavy workstation setup for video rendering and displays."),
        (8, "Android/Google", "mid-range", "Fitness tracking and wireless travel audio."),
        (9, "Apple", "premium", "High speed external drives and mobile camera gear."),
        (10, "Smart Home", "mid-range", "Basic smart plugs, bulbs, and kitchen appliances.")
    ]
    for cid, eco, bdg, nts in preferences:
        conn.execute(
            "INSERT INTO Preferences (customer_id, ecosystem, budget_tier, notes) VALUES (?, ?, ?, ?)",
            (cid, eco, bdg, nts)
        )

    tags = [
        (1, "4k-video-editing", "ai_agent"),
        (2, "budget-conscious", "ai_agent"),
        (3, "pc-gaming", "user"),
        (4, "portable-audio", "ai_agent"),
        (5, "smart-home-user", "user"),
        (6, "linux-user", "ai_agent"),
        (7, "4k-video-editing", "ai_agent"),
        (8, "fitness-tracking", "user"),
        (9, "photographer", "ai_agent"),
        (10, "apple-ecosystem", "user")
    ]

    for cid, tg, src in tags:
        conn.execute(
            "INSERT OR IGNORE INTO PreferenceTags (customer_id, tag_name, source) VALUES (?, ?, ?)",
            (cid, tg, src)
        )

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    seed_db()