"""
Database layer for the AI Product Consultant microservice.

This service has exclusive ownership of the three tables below. No other
OmniTech service reads or writes them directly - access is only through the
REST API in backend/main.py.

Tables
------
ConsultationSessions
    id          INTEGER  primary key           (session ID)
    user_id     TEXT     owner of the session
    title       TEXT     editable session title
    created_at  TIMESTAMP
    updated_at  TIMESTAMP

ChatLogs
    id            INTEGER  primary key          (message ID)
    session_id    INTEGER  -> ConsultationSessions.id
    sender        TEXT     'user' or 'ai'
    message_text  TEXT
    created_at    TIMESTAMP

SavedRecommendations
    id           INTEGER  primary key
    session_id   INTEGER  -> ConsultationSessions.id
    product_ids  TEXT     comma-separated catalog product ids
    summary      TEXT     generated summary of why the products fit
    tags         TEXT     comma-separated custom user tags
    created_at   TIMESTAMP
"""

import os
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.getenv(
    "DB_PATH", os.path.join(os.path.dirname(__file__), "consultant.db")
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS ConsultationSessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL DEFAULT 'guest',
    title      TEXT NOT NULL DEFAULT 'New Consultation',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ChatLogs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER NOT NULL,
    sender       TEXT NOT NULL CHECK (sender IN ('user', 'ai')),
    message_text TEXT NOT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES ConsultationSessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS SavedRecommendations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL,
    product_ids TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES ConsultationSessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chatlogs_session ON ChatLogs(session_id);
CREATE INDEX IF NOT EXISTS idx_savedrecs_session ON SavedRecommendations(session_id);
"""


def get_db():
    """Return a new SQLite connection with row access by column name.

    The schema DDL is applied on every connection. `CREATE TABLE IF NOT EXISTS`
    is a cheap no-op once the tables exist, and it means the service can never
    hit a "no such table" error - even if the database file is missing, empty,
    or was created by an older build.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def init_db():
    """Ensure the schema exists (also done lazily by get_db)."""
    get_db().close()


def seed_db():
    """Populate demo data once so the dashboard is not empty on first run.

    At least 10 rows are inserted into each of the three tables.
    """
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM ConsultationSessions").fetchone()[0] > 0:
        conn.close()
        return

    now = datetime.now()

    # --- ConsultationSessions: 10 rows across 3 users ---------------------- #
    sessions = [
        ("u-1001", "Laptop for 4K video editing", 12),
        ("u-1001", "Budget phone under $300", 11),
        ("u-1001", "Noise-cancelling headphones for the train", 9),
        ("u-1002", "Tablet for a first-year student", 8),
        ("u-1002", "Colour-accurate monitor for photo work", 7),
        ("u-1002", "Gaming headset with a clear mic", 6),
        ("u-1003", "Compact camera for travel", 5),
        ("u-1003", "Smartwatch for running", 4),
        ("u-1003", "Portable speaker for the garden", 2),
        ("u-1003", "Fast external drive for editing", 1),
    ]
    for user_id, title, days_ago in sessions:
        ts = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO ConsultationSessions (user_id, title, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, title, ts, ts),
        )

    # --- ChatLogs: 2 rows per session (20 total) ------------------------- #
    logs = [
        (1, "user", "I need a laptop that can handle 4K timelines in a video editor."),
        (1, "ai", "The Meridian Pro 16 (LAP-001) is built for that: 16-core CPU, "
                  "32GB RAM and a 4K screen. Around $2,399."),
        (2, "user", "What is the best phone I can get for under $300?"),
        (2, "ai", "The Pulse 5 (PHN-003) fits under $300 with a big 5000mAh battery "
                  "and a 90Hz screen. About $279."),
        (3, "user", "I want headphones that block out train noise on my commute."),
        (3, "ai", "The EchoStudio Over-Ear (AUD-002) has strong active noise "
                  "cancellation and 40h of battery. Around $349."),
        (4, "user", "My sibling starts university and needs a tablet for notes."),
        (4, "ai", "The Slate 11 (TAB-001) has a 120Hz screen and stylus support, "
                  "good for handwritten notes. About $599."),
        (5, "user", "I edit photos and need an accurate monitor."),
        (5, "ai", "The ClearView 27 4K (MON-001) covers 99% sRGB and has USB-C "
                  "power delivery. Around $429."),
        (6, "user", "Recommend a gaming headset with a good microphone."),
        (6, "ai", "The FieldMic Headset (AUD-003) has a detachable boom mic and "
                  "7.1 spatial audio. About $129."),
        (7, "user", "I want a small camera for travelling light."),
        (7, "ai", "The Vista X100 (CAM-001) is a compact APS-C camera with a fixed "
                  "prime lens and 4K60 video. Around $899."),
        (8, "user", "Which smartwatch is best for tracking runs?"),
        (8, "ai", "The Tempo Watch 2 (WEAR-001) has dual-band GPS and a 7-day "
                  "battery. About $329."),
        (9, "user", "I need a speaker I can leave outside."),
        (9, "ai", "The BoomBox Go (SPK-001) is IP67 rated with 24h of playtime. "
                  "Around $149."),
        (10, "user", "What is a fast drive for video editing scratch files?"),
        (10, "ai", "The WarpDrive 2TB SSD (STOR-001) runs at 2000MB/s over USB-C. "
                   "About $179."),
    ]
    for session_id, sender, text in logs:
        conn.execute(
            "INSERT INTO ChatLogs (session_id, sender, message_text) VALUES (?, ?, ?)",
            (session_id, sender, text),
        )

    # --- SavedRecommendations: 10 rows --------------------------------- #
    recs = [
        (1, "LAP-001", "Workstation laptop that handles 4K editing without throttling.",
         "video-editing,work,priority"),
        (2, "PHN-003,PHN-002", "Two budget-friendly phones; the Pulse 5 wins on "
                               "battery, the Aura SE on screen quality.",
         "budget,comparison"),
        (3, "AUD-002,AUD-001", "Over-ear for maximum isolation, earbuds for a lighter "
                               "carry.", "commute,noise-cancelling"),
        (4, "TAB-001", "Student tablet with stylus support for handwritten notes.",
         "student,notes"),
        (5, "MON-001", "Colour-accurate 4K panel for photo editing.",
         "photography,colour-accurate"),
        (6, "AUD-003", "Gaming headset with a detachable broadcast-quality mic.",
         "gaming,voice-chat"),
        (7, "CAM-001", "Compact travel camera with a bright prime lens.",
         "travel,photography"),
        (8, "WEAR-001", "Running watch with dual-band GPS and week-long battery.",
         "running,fitness"),
        (9, "SPK-001", "Weatherproof portable speaker for outdoor use.",
         "outdoor,durable"),
        (10, "STOR-001", "Fast pocket SSD for editing scratch disks.",
         "editing,storage"),
    ]
    for session_id, product_ids, summary, tags in recs:
        conn.execute(
            "INSERT INTO SavedRecommendations (session_id, product_ids, summary, tags) "
            "VALUES (?, ?, ?, ?)",
            (session_id, product_ids, summary, tags),
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    seed_db()
    print(f"Database initialised and seeded at {DB_PATH}")
