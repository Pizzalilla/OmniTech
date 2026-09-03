import os
import sys
from flask import Flask, render_template
from llm_client import OLLAMA_MODEL, create_chat_completion
from prompt_loader import load_prompt
from database.app import get_db_connection

app = Flask(__name__, template_folder="../templates")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


@app.route("/")
def index():
    return render_template("index.html", service_name="Student 5")

@app.post("/api/tickets/<int:ticket_id>/evaluate")
def ai_evaluate_ticket(ticket_id):
    conn = get_db_connection()
    ticket = conn.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    conn.close()
    try:
        system_prompt = load_prompt("system_prompt.txt")
        policy_rules_prompt = load_prompt("policy_rules_prompt.txt")
        task_prompt = load_prompt("task_prompt.txt")

        final_prompt = f"""
{task_prompt}

{policy_rules_prompt}

Product Category: {ticket["product_category"]}
Warranty Claim: {ticket["ticket_claim"]}
"""
        
        decision = create_chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": final_prompt},
            ],
            max_tokens=300,
            temperature=0.2,
            model=OLLAMA_MODEL,
        )
        return f"<p>{decision}</p>", 200
    except Exception as exc:
        return (
            "<p>Evaluation request failed.</p>"
            f"<pre>{exc}</pre>",
            503,
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
