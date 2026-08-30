import os
import sys

from flask import Flask, abort, jsonify, render_template, request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "database"))
from database import get_db, init_db, seed_db

import agent
import catalog

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

# Served at /static/style.css  (style.css lives in this service's own tree so the
# container ships it without the shared/ directory).
app = Flask(
    __name__,
    template_folder=os.path.join(FRONTEND_DIR, "templates"),
    static_folder=os.path.join(FRONTEND_DIR, "static"),
    static_url_path="/static",
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _session_or_404(conn, session_id):
    row = conn.execute(
        "SELECT * FROM ConsultationSessions WHERE id = ?", (session_id,)
    ).fetchone()
    if row is None:
        conn.close()
        abort(404, description="Session not found")
    return row


def _reco_view(row):
    """Expand a SavedRecommendations row into a template-friendly dict."""
    ids = [i for i in (row["product_ids"] or "").split(",") if i]
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "product_ids": ids,
        "products": catalog.get_many(ids),
        "summary": row["summary"],
        "tags": [t for t in (row["tags"] or "").split(",") if t],
        "created_at": row["created_at"],
    }


def _recos_for_session(conn, session_id):
    rows = conn.execute(
        "SELECT * FROM SavedRecommendations WHERE session_id = ? ORDER BY id DESC",
        (session_id,),
    ).fetchall()
    return [_reco_view(r) for r in rows]


def _is_htmx():
    return request.headers.get("HX-Request") == "true"


@app.errorhandler(400)
@app.errorhandler(404)
def _errors(err):
    if request.path.startswith("/api/"):
        return jsonify(error=err.description), err.code
    return err.description, err.code


# ── Pages ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", service_name="AI Product Consultant")


@app.route("/dashboard")
def dashboard():
    conn = get_db()
    sessions = conn.execute(
        "SELECT s.*, "
        "  (SELECT COUNT(*) FROM ChatLogs c WHERE c.session_id = s.id) AS message_count, "
        "  (SELECT COUNT(*) FROM SavedRecommendations r WHERE r.session_id = s.id) AS reco_count "
        "FROM ConsultationSessions s ORDER BY s.updated_at DESC"
    ).fetchall()
    reco_rows = conn.execute(
        "SELECT r.*, s.title AS session_title FROM SavedRecommendations r "
        "JOIN ConsultationSessions s ON s.id = r.session_id ORDER BY r.id DESC"
    ).fetchall()
    conn.close()
    recommendations = []
    for r in reco_rows:
        view = _reco_view(r)
        view["session_title"] = r["session_title"]
        recommendations.append(view)
    return render_template(
        "dashboard.html",
        service_name="AI Product Consultant",
        sessions=sessions,
        recommendations=recommendations,
    )


# ── REST API: Consultation sessions ──────────────────────────────────────────

@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    user_id = request.args.get("user_id")
    conn = get_db()
    if user_id:
        rows = conn.execute(
            "SELECT * FROM ConsultationSessions WHERE user_id = ? "
            "ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM ConsultationSessions ORDER BY updated_at DESC"
        ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/sessions", methods=["POST"])
def create_session():
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "New Consultation").strip() or "New Consultation"
    user_id = (body.get("user_id") or "guest").strip() or "guest"
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO ConsultationSessions (user_id, title) VALUES (?, ?)",
        (user_id, title),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM ConsultationSessions WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@app.route("/api/sessions/<int:session_id>", methods=["GET"])
def get_session(session_id):
    conn = get_db()
    session = _session_or_404(conn, session_id)
    messages = conn.execute(
        "SELECT id, sender, message_text, created_at FROM ChatLogs "
        "WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    recommendations = _recos_for_session(conn, session_id)
    conn.close()
    return jsonify({
        "session": dict(session),
        "messages": [dict(m) for m in messages],
        "recommendations": recommendations,
    })


@app.route("/api/sessions/<int:session_id>", methods=["PUT"])
def update_session(session_id):
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    if not title:
        abort(400, description="Title is required")
    conn = get_db()
    _session_or_404(conn, session_id)
    conn.execute(
        "UPDATE ConsultationSessions SET title = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (title, session_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM ConsultationSessions WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()
    return jsonify(dict(row))


@app.route("/api/sessions/<int:session_id>", methods=["DELETE"])
def delete_session(session_id):
    conn = get_db()
    _session_or_404(conn, session_id)
    conn.execute("DELETE FROM ConsultationSessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Session deleted"})


# ── REST API: Chat logs ──────────────────────────────────────────────────────

@app.route("/api/sessions/<int:session_id>/messages", methods=["GET"])
def list_messages(session_id):
    conn = get_db()
    _session_or_404(conn, session_id)
    rows = conn.execute(
        "SELECT id, sender, message_text, created_at FROM ChatLogs "
        "WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/sessions/<int:session_id>/messages", methods=["POST"])
def create_message(session_id):
    body = request.get_json(silent=True) or {}
    sender = body.get("sender")
    text = (body.get("message_text") or "").strip()
    if sender not in ("user", "ai") or not text:
        abort(400, description="sender ('user'|'ai') and message_text are required")
    conn = get_db()
    _session_or_404(conn, session_id)
    cur = conn.execute(
        "INSERT INTO ChatLogs (session_id, sender, message_text) VALUES (?, ?, ?)",
        (session_id, sender, text),
    )
    conn.execute(
        "UPDATE ConsultationSessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (session_id,),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, sender, message_text, created_at FROM ChatLogs WHERE id = ?",
        (cur.lastrowid,),
    ).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@app.route("/api/sessions/<int:session_id>/messages", methods=["DELETE"])
def clear_messages(session_id):
    """Delete the chat history for a session, keeping the session itself."""
    conn = get_db()
    session = _session_or_404(conn, session_id)
    conn.execute("DELETE FROM ChatLogs WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()
    if _is_htmx():
        return render_template("partials/messages.html", messages=[])
    return jsonify({"message": "Chat history cleared"})


@app.route("/api/messages/<int:message_id>", methods=["DELETE"])
def delete_message(message_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM ChatLogs WHERE id = ?", (message_id,)
    ).fetchone()
    if row is None:
        conn.close()
        abort(404, description="Message not found")
    conn.execute("DELETE FROM ChatLogs WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Message deleted"})


# ── REST API: Saved recommendations ──────────────────────────────────────────

@app.route("/api/sessions/<int:session_id>/recommendations", methods=["GET"])
def list_recommendations(session_id):
    conn = get_db()
    _session_or_404(conn, session_id)
    recos = _recos_for_session(conn, session_id)
    conn.close()
    return jsonify(recos)


@app.route("/api/recommendations", methods=["POST"])
def create_recommendation():
    body = request.get_json(silent=True) or {}
    session_id = body.get("session_id")
    product_ids = body.get("product_ids") or []
    summary = (body.get("summary") or "").strip()
    tags = body.get("tags") or ""
    if isinstance(tags, list):
        tags = ",".join(t.strip() for t in tags if t.strip())
    if not session_id or not isinstance(product_ids, list) or not product_ids:
        abort(400, description="session_id and a non-empty product_ids list are required")
    clean_ids = [pid for pid in product_ids if pid in catalog.VALID_IDS]
    if not clean_ids:
        abort(400, description="No product_ids match the catalog")
    conn = get_db()
    _session_or_404(conn, session_id)
    cur = conn.execute(
        "INSERT INTO SavedRecommendations (session_id, product_ids, summary, tags) "
        "VALUES (?, ?, ?, ?)",
        (session_id, ",".join(clean_ids), summary, tags),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM SavedRecommendations WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    conn.close()
    return jsonify(_reco_view(row)), 201


@app.route("/api/recommendations/<int:reco_id>", methods=["PUT"])
def update_recommendation(reco_id):
    body = request.get_json(silent=True) or {}
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM SavedRecommendations WHERE id = ?", (reco_id,)
    ).fetchone()
    if row is None:
        conn.close()
        abort(404, description="Recommendation not found")
    tags = body.get("tags", row["tags"])
    if isinstance(tags, list):
        tags = ",".join(t.strip() for t in tags if t.strip())
    summary = body.get("summary", row["summary"])
    conn.execute(
        "UPDATE SavedRecommendations SET tags = ?, summary = ? WHERE id = ?",
        (tags, summary, reco_id),
    )
    conn.commit()
    updated = conn.execute(
        "SELECT * FROM SavedRecommendations WHERE id = ?", (reco_id,)
    ).fetchone()
    conn.close()
    return jsonify(_reco_view(updated))


@app.route("/api/recommendations/<int:reco_id>/tags", methods=["POST"])
def add_recommendation_tag(reco_id):
    """Add a single preference tag. Accepts a form field 'tag' (used by HTMX)
    or JSON {"tag": "..."}."""
    tag = (request.form.get("tag") or (request.get_json(silent=True) or {}).get("tag") or "")
    tag = tag.strip().lower().replace(" ", "-")
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM SavedRecommendations WHERE id = ?", (reco_id,)
    ).fetchone()
    if row is None:
        conn.close()
        abort(404, description="Recommendation not found")
    tags = [t for t in (row["tags"] or "").split(",") if t]
    if tag and tag not in tags:
        tags.append(tag)
    conn.execute(
        "UPDATE SavedRecommendations SET tags = ? WHERE id = ?",
        (",".join(tags), reco_id),
    )
    conn.commit()
    updated = conn.execute(
        "SELECT * FROM SavedRecommendations WHERE id = ?", (reco_id,)
    ).fetchone()
    conn.close()
    if _is_htmx():
        return render_template("partials/reco.html", r=_reco_view(updated))
    return jsonify(_reco_view(updated))


@app.route("/api/recommendations/<int:reco_id>", methods=["DELETE"])
def delete_recommendation(reco_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM SavedRecommendations WHERE id = ?", (reco_id,)
    ).fetchone()
    if row is None:
        conn.close()
        abort(404, description="Recommendation not found")
    conn.execute("DELETE FROM SavedRecommendations WHERE id = ?", (reco_id,))
    conn.commit()
    conn.close()
    if _is_htmx():
        return ("", 200)
    return jsonify({"message": "Recommendation deleted"})


# ── Agentic AI: Plan → Act → Observe → Adapt ─────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def chat():
    """Run one consultation turn through the agentic loop.

    Accepts JSON {session_id, message} or an HTMX form post with the same
    fields. Returns JSON by default, or an HTML fragment when called from HTMX.
    """
    if request.is_json:
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id")
        user_message = (data.get("message") or "").strip()
    else:
        session_id = request.form.get("session_id", type=int)
        user_message = (request.form.get("message") or "").strip()

    if not session_id or not user_message:
        abort(400, description="session_id and message are required")

    conn = get_db()
    _session_or_404(conn, session_id)

    conn.execute(
        "INSERT INTO ChatLogs (session_id, sender, message_text) VALUES (?, 'user', ?)",
        (session_id, user_message),
    )
    conn.commit()

    history = conn.execute(
        "SELECT sender, message_text FROM ChatLogs WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()

    result = agent.run_consultation(user_message, [dict(h) for h in history])
    ai_text = result["reply"]

    conn.execute(
        "INSERT INTO ChatLogs (session_id, sender, message_text) VALUES (?, 'ai', ?)",
        (session_id, ai_text),
    )

    saved_reco = None
    if result["recommended_product_ids"]:
        cur = conn.execute(
            "INSERT INTO SavedRecommendations (session_id, product_ids, summary, tags) "
            "VALUES (?, ?, ?, '')",
            (session_id, ",".join(result["recommended_product_ids"]), result["summary"]),
        )
        saved_reco = conn.execute(
            "SELECT * FROM SavedRecommendations WHERE id = ?", (cur.lastrowid,)
        ).fetchone()

    conn.execute(
        "UPDATE ConsultationSessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (session_id,),
    )
    conn.commit()
    recommendations = _recos_for_session(conn, session_id)
    conn.close()

    if _is_htmx():
        return render_template(
            "partials/chat_turn.html",
            user_message=user_message,
            ai_reply=ai_text,
            meta=result["meta"],
            recommendations=recommendations,
        )
    return jsonify({
        "reply": ai_text,
        "recommended_product_ids": result["recommended_product_ids"],
        "summary": result["summary"],
        "saved_recommendation": _reco_view(saved_reco) if saved_reco else None,
        "meta": result["meta"],
    })


# ── HTMX partials ────────────────────────────────────────────────────────────

@app.route("/partials/session-list")
def partial_session_list():
    active_id = request.args.get("active", type=int)
    conn = get_db()
    sessions = conn.execute(
        "SELECT id, title, user_id, created_at FROM ConsultationSessions "
        "ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return render_template(
        "partials/session_list.html", sessions=sessions, active_id=active_id
    )


@app.route("/partials/chat/<int:session_id>")
def partial_chat(session_id):
    conn = get_db()
    session = _session_or_404(conn, session_id)
    messages = conn.execute(
        "SELECT id, sender, message_text, created_at FROM ChatLogs "
        "WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    recommendations = _recos_for_session(conn, session_id)
    conn.close()
    return render_template(
        "partials/chat_panel.html",
        session=session,
        messages=messages,
        recommendations=recommendations,
    )


@app.route("/partials/recommendations/<int:session_id>")
def partial_recommendations(session_id):
    conn = get_db()
    _session_or_404(conn, session_id)
    recommendations = _recos_for_session(conn, session_id)
    conn.close()
    return render_template(
        "partials/recommendations.html", recommendations=recommendations
    )


# ── Startup ──────────────────────────────────────────────────────────────────

with app.app_context():
    init_db()
    seed_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
