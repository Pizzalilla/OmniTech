import os
import sys
STUDENT5_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STUDENT5_DIR)
from flask import Flask, render_template, jsonify, send_from_directory
from llm_client import OLLAMA_MODEL, create_chat_completion
from prompt_loader import load_prompt
from database.app import get_db_connection

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# app = Flask(
#     __name__,
#     template_folder=os.path.join(BASE_DIR, "frontend", "templates"),
#     static_folder=os.path.join(os.path.dirname(BASE_DIR), "shared", "frontend", "css")
# )
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "frontend", "templates"),
    static_folder=os.path.join(BASE_DIR, "frontend", "css")
)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

@app.route("/")
def index():
    conn = get_db_connection()

    tickets = conn.execute(
        "SELECT * FROM tickets ORDER BY ticket_id"
    ).fetchall()

    conn.close()

    return render_template(
        "index.html",
        tickets=tickets
    )

@app.route("/ai-evaluation")
def ai_evaluation():
    conn = get_db_connection()

    tickets = conn.execute(
        "SELECT * FROM tickets ORDER BY ticket_id"
    ).fetchall()

    conn.close()

    return render_template("index.html", tickets=tickets)

@app.post("/api/tickets/<int:ticket_id>/evaluate")
def ai_evaluate_ticket(ticket_id):
    try:
        conn = get_db_connection()

        ticket = conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?",
            (ticket_id,)
        ).fetchone()

        conn.close()

        if ticket is None:
            return jsonify({
                "success": False,
                "error": f"Ticket {ticket_id} not found."
            }), 404

        system_prompt = load_prompt("system_prompt.txt")
        policy_rules_prompt = load_prompt("policy_rules_prompt.txt")
        task_prompt = load_prompt("task_prompt.txt")

        final_prompt = f"""
{task_prompt}

{policy_rules_prompt}

Product Category: {ticket["product_category"]}
Warranty Claim: {ticket["ticket_claim"]}
"""

        ai_response = create_chat_completion(
            [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": final_prompt
                }
            ],
            max_tokens=300,
            temperature=0.2,
            model=OLLAMA_MODEL,
        )

        ai_response = ai_response.strip()
        decision = ""
        reasoning = ""
        for line in ai_response.splitlines():
            if line.lower().startswith("decision:"):
                decision = line.split(":", 1)[1].strip()

            elif line.lower().startswith("reasoning:"):
                reasoning = line.split(":", 1)[1].strip()

        return jsonify({
            "success": True,
            "ticket_id": ticket_id,
            "decision": decision,
            "reasoning": reasoning
        }), 200

    except Exception as exc:
        print(f"AI evaluation failed for ticket {ticket_id}: {exc}")

        return jsonify({
            "success": False,
            "error": "Evaluation request failed."
        }), 503

@app.route("/shared/css/<path:filename>")
def shared_css(filename):
    return send_from_directory(
        os.path.join(
            os.path.dirname(BASE_DIR),
            "shared",
            "frontend",
            "css"
        ),
        filename
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=True)
