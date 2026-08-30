import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "consultant.db"))


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT 'New Consultation',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS recommendation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            recommendation_text TEXT NOT NULL,
            tags TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()
    existing = conn.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    now = datetime.now()

    sessions = [
        ("Best laptop for video editing", now - timedelta(days=10)),
        ("Budget smartphone under $300", now - timedelta(days=9)),
        ("Gaming headset comparison", now - timedelta(days=8)),
        ("4K TV for living room", now - timedelta(days=7)),
        ("Wireless earbuds for running", now - timedelta(days=6)),
        ("Smart home starter kit", now - timedelta(days=5)),
        ("Mechanical keyboard for coding", now - timedelta(days=4)),
        ("Tablet for university students", now - timedelta(days=3)),
        ("Portable Bluetooth speaker", now - timedelta(days=2)),
        ("Webcam for remote work", now - timedelta(days=1)),
    ]

    for title, created_at in sessions:
        ts = created_at.strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO chat_sessions (title, created_at, updated_at) VALUES (?, ?, ?)",
            (title, ts, ts),
        )

    messages = [
        (1, "user", "I need a laptop that can handle 4K video editing in Premiere Pro."),
        (1, "assistant", "For 4K video editing in Premiere Pro, I recommend the Apple MacBook Pro 16\" with M3 Pro chip. It offers excellent sustained performance, a stunning Liquid Retina XDR display, and up to 22 hours of battery life. The 18GB unified memory handles multi-stream 4K timelines smoothly. Price: around $2,499."),
        (2, "user", "What's the best phone I can get for under $300?"),
        (2, "assistant", "The Google Pixel 7a is an excellent choice under $300. It features a 6.1\" OLED display, Google Tensor G2 chip, 8GB RAM, and a 64MP camera with Google's computational photography. You also get 5 years of security updates. Currently priced around $279."),
        (3, "user", "I want a gaming headset with good surround sound and a clear mic."),
        (3, "assistant", "The HyperX Cloud III is a top pick at $99. It delivers DTS Headphone:X spatial audio, a detachable noise-cancelling microphone, and memory foam ear cushions for long sessions. Compatible with PC, PS5, Xbox, and Switch via USB-C or 3.5mm."),
        (4, "user", "Looking for a 55-inch 4K TV, mainly for movies and sports."),
        (4, "assistant", "The LG C3 55\" OLED TV is ideal for movies and sports. Its self-lit OLED pixels deliver perfect blacks and infinite contrast. The 120Hz refresh rate with HDMI 2.1 keeps fast sports action smooth. Dolby Vision and Atmos support make it a home cinema powerhouse. Around $1,296."),
        (5, "user", "Need earbuds that stay in during runs and are sweatproof."),
        (5, "assistant", "The Jabra Elite 8 Active are built for runners. They have an IP68 dust and water rating, adaptive ANC, and Jabra ShakeGrip technology that keeps them locked in during movement. Battery life is 8 hours with ANC on, 32 hours total with the case. Price: $199."),
        (6, "user", "I want to start automating my home. Where do I begin?"),
        (6, "assistant", "Start with an Amazon Echo Hub as your central controller ($149). Add a few Philips Hue smart bulbs ($49 starter kit) and a Ring Video Doorbell ($99). This gives you voice-controlled lighting, a smart display dashboard, and front-door security — all working together via Alexa. Total: around $297."),
        (7, "user", "Recommend a mechanical keyboard that's quiet enough for an office."),
        (7, "assistant", "The Keychron Q1 Pro with Gateron Brown switches is excellent for office use. Brown switches give you tactile feedback without the loud click. It has a gasket-mount design for a softer typing feel, wireless Bluetooth, and a hot-swappable PCB for future switch changes. Around $199."),
        (8, "user", "My daughter needs a tablet for uni — note-taking, reading, light multitasking."),
        (8, "assistant", "The iPad Air M2 (11\") is perfect for university. Pair it with an Apple Pencil Pro for handwritten notes in apps like GoodNotes. The M2 chip handles multitasking easily, the 11\" Liquid Retina display is great for reading PDFs, and it lasts all day on a single charge. Starting at $599."),
        (9, "user", "What portable speaker has the best sound for its size?"),
        (9, "assistant", "The JBL Charge 5 delivers room-filling sound from a portable package. It has a dedicated tweeter and dual bass radiators, IP67 waterproof rating, 20 hours of playtime, and can charge your phone via USB. It also supports JBL PartyBoost to link multiple speakers. Price: $179."),
        (10, "user", "I need a good webcam for Zoom calls. 1080p minimum."),
        (10, "assistant", "The Logitech Brio 300 is a solid 1080p webcam at $69. It has auto light correction for dim rooms, a built-in privacy shutter, and a noise-reducing mono mic. It connects via USB-C and works with Zoom, Teams, and Google Meet out of the box."),
    ]

    for session_id, role, content in messages:
        conn.execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )

    recommendations = [
        (1, "MacBook Pro 16\" M3 Pro", "Laptops", "Ideal for 4K video editing with sustained performance and long battery life.", "video-editing,apple,professional"),
        (2, "Google Pixel 7a", "Smartphones", "Best sub-$300 phone with flagship camera and long software support.", "budget,google,photography"),
        (3, "HyperX Cloud III", "Audio", "Versatile gaming headset with spatial audio and cross-platform support.", "gaming,headset,surround-sound"),
        (4, "LG C3 55\" OLED", "Televisions", "Premium OLED TV with perfect blacks and smooth sports motion.", "4k,oled,home-cinema"),
        (5, "Jabra Elite 8 Active", "Audio", "Durable running earbuds with IP68 rating and adaptive ANC.", "running,waterproof,anc"),
        (6, "Amazon Echo Hub + Hue + Ring", "Smart Home", "Affordable smart home starter bundle with voice control and security.", "smart-home,alexa,starter-kit"),
        (7, "Keychron Q1 Pro", "Peripherals", "Quiet mechanical keyboard with wireless connectivity and hot-swap switches.", "mechanical,office,wireless"),
        (8, "iPad Air M2 11\"", "Tablets", "Versatile university tablet with Apple Pencil Pro support.", "tablet,student,apple"),
        (9, "JBL Charge 5", "Audio", "Portable speaker with powerful sound, waterproofing, and phone charging.", "portable,waterproof,bluetooth"),
        (10, "Logitech Brio 300", "Peripherals", "Affordable 1080p webcam with auto light correction.", "webcam,remote-work,1080p"),
    ]

    for session_id, product, category, text, tags in recommendations:
        conn.execute(
            "INSERT INTO recommendation_logs (session_id, product_name, category, recommendation_text, tags) VALUES (?, ?, ?, ?, ?)",
            (session_id, product, category, text, tags),
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    seed_db()
    print(f"Database initialised and seeded at {DB_PATH}")
