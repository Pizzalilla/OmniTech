import os
import sys
import requests
from flask import Flask, render_template, request, jsonify

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "database"))
from database import get_db, init_db, seed_db

SHARED_CSS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "shared", "frontend")
app = Flask(__name__, template_folder="../frontend/templates", static_folder=SHARED_CSS_DIR, static_url_path="/static")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")

SYSTEM_PROMPT = (
    "You are an AI Product Consultant for OmniTech Marketplace, a consumer electronics store. "
    "Help customers find the right products by asking about their needs, budget, and preferences. "
    "Provide specific product recommendations with model names, key specs, and approximate prices. "
    "Be concise and helpful. When recommending a product, always include: "
    "1) Product name, 2) Key specifications, 3) Why it suits the customer, 4) Approximate price."
)


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", service_name="AI Product Consultant")


# ── CRUD: Chat Sessions ───────────────────────────────────────────────────────

@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    conn = get_db()
    sessions = conn.execute(
        "SELECT id, title, created_at, updated_at FROM chat_sessions ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(s) for s in sessions])


@app.route("/api/sessions", methods=["POST"])
def create_session():
    title = (request.json or {}).get("title", "New Consultation")
    conn = get_db()
    cur = conn.execute("INSERT INTO chat_sessions (title) VALUES (?)", (title,))
    session_id = cur.lastrowid
    conn.commit()
    session = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return jsonify(dict(session)), 201


@app.route("/api/sessions/<int:session_id>", methods=["GET"])
def get_session(session_id):
    conn = get_db()
    session = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    if not session:
        conn.close()
        return jsonify({"error": "Session not found"}), 404
    messages = conn.execute(
        "SELECT id, role, content, created_at FROM chat_messages WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    ).fetchall()
    recommendations = conn.execute(
        "SELECT id, product_name, category, recommendation_text, tags, created_at FROM recommendation_logs WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    ).fetchall()
    conn.close()
    return jsonify({
        "session": dict(session),
        "messages": [dict(m) for m in messages],
        "recommendations": [dict(r) for r in recommendations],
    })


@app.route("/api/sessions/<int:session_id>", methods=["PUT"])
def update_session(session_id):
    title = (request.json or {}).get("title")
    if not title:
        return jsonify({"error": "Title is required"}), 400
    conn = get_db()
    conn.execute(
        "UPDATE chat_sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (title, session_id),
    )
    conn.commit()
    session = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(dict(session))


@app.route("/api/sessions/<int:session_id>", methods=["DELETE"])
def delete_session(session_id):
    conn = get_db()
    session = conn.execute("SELECT id FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    if not session:
        conn.close()
        return jsonify({"error": "Session not found"}), 404
    conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Session deleted"}), 200


# ── CRUD: Recommendation Logs ─────────────────────────────────────────────────

@app.route("/api/recommendations/<int:rec_id>/tags", methods=["PUT"])
def update_recommendation_tags(rec_id):
    tags = (request.json or {}).get("tags", "")
    conn = get_db()
    rec = conn.execute("SELECT id FROM recommendation_logs WHERE id = ?", (rec_id,)).fetchone()
    if not rec:
        conn.close()
        return jsonify({"error": "Recommendation not found"}), 404
    conn.execute("UPDATE recommendation_logs SET tags = ? WHERE id = ?", (tags, rec_id))
    conn.commit()
    updated = conn.execute("SELECT * FROM recommendation_logs WHERE id = ?", (rec_id,)).fetchone()
    conn.close()
    return jsonify(dict(updated))


# ── Agentic AI: Plan → Act → Observe → Adapt ──────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json or {}
    session_id = data.get("session_id")
    user_message = data.get("message", "").strip()

    if not session_id or not user_message:
        return jsonify({"error": "session_id and message are required"}), 400

    conn = get_db()
    session = conn.execute("SELECT id FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    if not session:
        conn.close()
        return jsonify({"error": "Session not found"}), 404

    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'user', ?)",
        (session_id, user_message),
    )
    conn.commit()

    # ── PLAN: build the prompt with conversation history ──
    history = conn.execute(
        "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    ).fetchall()

    prompt_parts = [f"System: {SYSTEM_PROMPT}"]
    for msg in history:
        prefix = "Customer" if msg["role"] == "user" else "Consultant"
        prompt_parts.append(f"{prefix}: {msg['content']}")
    prompt_parts.append("Consultant:")
    full_prompt = "\n".join(prompt_parts)

    # ── ACT: call the Ollama LLM ──
    try:
        ollama_response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": full_prompt, "stream": False},
            timeout=120,
        )
        ollama_response.raise_for_status()
        result = ollama_response.json()
    except requests.RequestException as e:
        fallback = "I'm sorry, the AI service is temporarily unavailable. Please try again shortly."
        conn.execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'assistant', ?)",
            (session_id, fallback),
        )
        conn.execute(
            "UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,),
        )
        conn.commit()
        conn.close()
        return jsonify({"role": "assistant", "content": fallback, "error": str(e)}), 200

    # ── OBSERVE: validate the LLM response ──
    assistant_text = result.get("response", "").strip()
    if not assistant_text:
        assistant_text = "I wasn't able to generate a response. Could you rephrase your question?"

    # ── ADAPT: save response and optionally log a recommendation ──
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'assistant', ?)",
        (session_id, assistant_text),
    )
    conn.execute(
        "UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (session_id,),
    )
    conn.commit()
    conn.close()

    return jsonify({"role": "assistant", "content": assistant_text})


@app.route("/api/chat/recommend", methods=["POST"])
def log_recommendation():
    data = request.json or {}
    required = ["session_id", "product_name", "category", "recommendation_text"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO recommendation_logs (session_id, product_name, category, recommendation_text, tags) VALUES (?, ?, ?, ?, ?)",
        (data["session_id"], data["product_name"], data["category"], data["recommendation_text"], data.get("tags", "")),
    )
    conn.commit()
    rec = conn.execute("SELECT * FROM recommendation_logs WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(rec)), 201


# ── HTMX Partials ─────────────────────────────────────────────────────────────

@app.route("/partials/session-list")
def partial_session_list():
    conn = get_db()
    sessions = conn.execute(
        "SELECT id, title, created_at FROM chat_sessions ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return render_template("partials/session_list.html", sessions=sessions)


@app.route("/partials/chat/<int:session_id>")
def partial_chat(session_id):
    conn = get_db()
    session = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    messages = conn.execute(
        "SELECT role, content, created_at FROM chat_messages WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    ).fetchall()
    recommendations = conn.execute(
        "SELECT id, product_name, category, tags FROM recommendation_logs WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    ).fetchall()
    conn.close()
    return render_template(
        "partials/chat_panel.html",
        session=session,
        messages=messages,
        recommendations=recommendations,
    )


# ── Startup ────────────────────────────────────────────────────────────────────

with app.app_context():
    init_db()
    seed_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
