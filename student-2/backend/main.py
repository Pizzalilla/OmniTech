import os
import sys
import requests
import json
from flask import Flask, abort, jsonify, render_template, request, render_template_string
from mcp_client import McpClient, McpError

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
RAG_SERVER_URL = os.getenv("RAG_SERVER_URL", "http://host.docker.internal:6002")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://host.docker.internal:6003")
MULTI_AGENT_URL = os.getenv("MULTI_AGENT_URL", "http://host.docker.internal:6004")

sys.path.insert(0, os.path.join(BASE_DIR, "database"))
from database import get_db, init_db, seed_db
import agent

app = Flask(
    __name__,
    template_folder=FRONTEND_DIR,
    static_folder=os.path.join(FRONTEND_DIR, "css"),
    static_url_path="/css"
)

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/customers", methods=["GET"])
def get_all_customers():
    conn = get_db()
    customers = conn.execute("SELECT * FROM Customers ORDER BY id DESC").fetchall()
    conn.close()
    
    html = """
    <table class='data-table' style='width: 100%; table-layout: fixed; word-wrap: break-word;'>
        <thead>
            <tr>
                <th style='width: 15%;'>ID</th>
                <th style='width: 30%;'>Name</th>
                <th style='width: 35%;'>Email</th>
                <th style='width: 20%; text-align: center;'>Action</th>
            </tr>
        </thead>
        <tbody>
    """
    for c in customers:
        html += f"""
        <tr id='customer-row-{c['id']}'>
            <td><strong>#{c['id']}</strong></td>
            <td style='word-wrap: break-word;'>{c['first_name']} {c['last_name']}</td>
            <td style='word-wrap: break-word; font-size: 0.85rem;'>{c['email']}</td>
            <td style='text-align: center;'>
                <button class='btn' style='padding: 0.25rem 0.4rem; font-size: 0.75rem;'
                        hx-get='/customers/{c["id"]}/edit'
                        hx-target='#customer-row-{c["id"]}'
                        hx-swap='outerHTML'>
                    Update
                </button>
                <button class='btn btn-danger' style='padding: 0.25rem 0.4rem; font-size: 0.75rem;'
                        hx-delete='/customers/{c['id']}' 
                        hx-target='#students-result' 
                        hx-confirm='Are you sure you want to delete this customer account?'>
                    Delete
                </button>
            </td>
        </tr>"""
    html += "</tbody></table>"
    return html



@app.route("/customers/<int:customer_id>/edit", methods=["GET"])
def edit_customer_row(customer_id):
    conn = get_db()
    c = conn.execute("SELECT * FROM Customers WHERE id = ?", (customer_id,)).fetchone()
    conn.close()

    if not c:
        return "<tr><td colspan='4'>Customer not found.</td></tr>"

    return f"""
    <tr id='customer-row-{c['id']}'>
        <td><strong>#{c['id']}</strong></td>
        <td>
            <input type='text' name='first_name' id='fn-{c['id']}' value='{c['first_name']}' style='width:48%; font-size:0.8rem;'>
            <input type='text' name='last_name' id='ln-{c['id']}' value='{c['last_name']}' style='width:48%; font-size:0.8rem;'>
        </td>
        <td>
            <input type='email' name='email' id='em-{c['id']}' value='{c['email']}' style='width:95%; font-size:0.8rem;'>
        </td>
        <td style='text-align: center;'>
            <button class='btn' style='padding: 0.25rem 0.4rem; font-size: 0.75rem;'
                    hx-put='/customers/{c['id']}'
                    hx-include='#fn-{c['id']}, #ln-{c['id']}, #em-{c['id']}'
                    hx-target='#students-result'>
                Save
            </button>
            <button class='btn' style='padding: 0.25rem 0.4rem; font-size: 0.75rem;'
                    hx-get='/customers'
                    hx-target='#students-result'>
                Cancel
            </button>
        </td>
    </tr>"""



@app.route("/customers/<int:customer_id>", methods=["PUT"])
def update_customer_profile(customer_id):

    fn = (request.form.get("first_name") or request.form.get(f"fn-{customer_id}") or "").strip()
    ln = (request.form.get("last_name") or request.form.get(f"ln-{customer_id}") or "").strip()
    email = (request.form.get("email") or request.form.get(f"em-{customer_id}") or "").strip()

    if not fn or not ln or not email:
        resp = app.make_response(get_all_customers())
        resp.headers["HX-Trigger"] = '{"showValidationAlert": "First Name, Last Name, and Email are required."}'
        return resp

    conn = get_db()
    try:
        conn.execute(
            "UPDATE Customers SET first_name=?, last_name=?, email=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (fn, ln, email, customer_id)
        )
        conn.commit()
        conn.close()

        return get_all_customers()
    
    except Exception as e:
        conn.close()
        resp = app.make_response(get_all_customers())
        resp.headers["HX-Trigger"] = f'{{"showValidationAlert": "Failed to update profile: {str(e)}"}}'
        return resp


@app.route("/customers", methods=["POST"])
def create_customer_profile():
    fn = request.form.get("first_name", "").strip()
    ln = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    street = request.form.get("shipping_street", "").strip()
    city = request.form.get("shipping_city", "").strip()
    state = request.form.get("shipping_state", "").strip()
    postcode = request.form.get("shipping_postcode", "").strip()

    if not fn or not ln or not email:
        resp = app.make_response("")
        resp.headers["HX-Trigger"] = '{"showValidationAlert": "First Name, Last Name, and Email are required."}'
        return resp

    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO Customers (first_name, last_name, email, phone, shipping_street, shipping_city, shipping_state, shipping_postcode) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (fn, ln, email, phone, street, city, state, postcode)
        )
        conn.commit()
        cid = cur.lastrowid
        conn.close()
        
        resp = app.make_response(f"<div class='panel'><strong>Success:</strong> Created customer profile #{cid}.</div>")
        resp.headers["HX-Trigger"] = "refreshCustomers"
        return resp
        
    except Exception:
        conn.close()
        resp = app.make_response("")
        resp.headers["HX-Trigger"] = '{"showValidationAlert": "Failed to create account. Email may already be registered."}'
        return "<div class='error'>Failed to create account</div>"


@app.route("/customers/by-id", methods=["GET"])
def get_customer_by_id():
    cid = request.args.get("customer_id", "").strip()
    if not cid:
        return "<div class='error'>Invalid Customer</div>"
    
    conn = get_db()
    customer = conn.execute("SELECT * FROM Customers WHERE id = ?", (cid,)).fetchone()
    if not customer:
        conn.close()
        return f"<div class='error'>Customer #{cid} not found.</div>"
        
    preferences = conn.execute("SELECT * FROM Preferences WHERE customer_id = ?", (cid,)).fetchall()
    tags = conn.execute("SELECT * FROM PreferenceTags WHERE customer_id = ?", (cid,)).fetchall()
    conn.close()

    return render_customer_profile(customer, preferences, tags)


@app.route("/generate-ai-suggestions", methods=["POST"])
def generate_ai_suggestions():
    cid = request.form.get("customer_id", "").strip()
    if not cid:
        return "<div class='error'>Please enter a customer ID.</div>"

    # 1. Gather Evidence Locally
    conn = get_db()
    customer = conn.execute("SELECT * FROM Customers WHERE id = ?", (cid,)).fetchone()
    if not customer:
        conn.close()
        return f"<div class='error'>Customer #{cid} not found.</div>"
    preferences = conn.execute("SELECT * FROM Preferences WHERE customer_id = ?", (cid,)).fetchall()
    conn.close()

    # Gather RAG Context for tagging rules (Bumped timeout to 15s)
    rag_rules = "No tagging rules found."
    try:
        rag_resp = requests.post(f"{RAG_SERVER_URL}/rag/query", 
                                 json={"query": "What are the allowed system categories and tagging rules for customer profiles?"}, 
                                 timeout=15)
        if rag_resp.ok:
            rag_rules = rag_resp.json().get("answer", rag_rules)
    except requests.RequestException:
        pass

    evidence = {
        "profile": dict(customer),
        "preferences": [dict(p) for p in preferences],
        "system_rules": rag_rules
    }

    # 2. Start the Multi-Agent Workflow
    task = "Analyze the customer profile and preferences. Output a JSON object with 'recommended_tags' (list of valid strings based on system rules) and 'reasoning' (string)."
    
    try:
        resp = requests.post(f"{MULTI_AGENT_URL}/workflow/start", 
                             json={"student": "student-2", "task": task, "evidence": evidence}, 
                             timeout=120)
        
        workflow = resp.json()
        
        # Wrap the HTML in a Flask response object so we can add headers
        response = app.make_response(render_workflow_status(workflow, cid))
        
        # This tells HTMX to automatically click the "Refresh" button on the dashboard for you
        response.headers["HX-Trigger"] = "refreshPendingList"
        return response
        
    except requests.exceptions.ReadTimeout:
        return "<div class='error'>The AI is taking too long to respond.</div>"
    except Exception as e:
        return f"<div class='error'>Failed to start AI workflow: {str(e)}</div>"
    
@app.route("/api/agent/status/<workflow_id>", methods=["GET"])
def check_workflow_status(workflow_id):
    cid = request.args.get("customer_id")
    try:
        resp = requests.get(f"{MULTI_AGENT_URL}/workflow/{workflow_id}", timeout=5)
        if resp.status_code == 404:
            return "<div class='error'>Workflow not found.</div>", 404
        return render_workflow_status(resp.json(), cid)
    except requests.RequestException:
        return "<div class='error'>Failed to reach AI Server.</div>", 503

@app.route("/apply-tags", methods=["POST"])
def apply_tags():
    cid = request.form.get("customer_id", "").strip()
    tags_str = request.form.get("tags", "").strip()
    
    if not cid or not tags_str:
        return "<div class='error'>Missing customer ID</div>"

    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    conn = get_db()
    
    for tag_name in tags:
        try:
            conn.execute("INSERT OR IGNORE INTO PreferenceTags (customer_id, tag_name, source) VALUES (?, ?, 'ai_agent')", (cid, tag_name))
        except Exception as e:
            print(f"Warning: Failed to save preference tag: {e}")

    conn.commit()
    updated_tags = conn.execute("SELECT * FROM PreferenceTags WHERE customer_id = ?", (cid,)).fetchall()
    conn.close()

    html = "<div class='panel'>"
    html += "<h4>Applied Suggestions to Profile</h4>"
    html += "<p style='font-size:0.9rem; margin-top:0.35rem;'><strong>Active Profile Preference Tags:</strong></p><p style='margin-top:0.25rem;'>"

    for tag in updated_tags:
        html += f"<span class='badge' style='background:#10b981; color:white; margin-right:4px;'>{tag['tag_name']}</span>"
    html += "</p></div>"
    return html


@app.route("/api/customers", methods=["GET"])
def api_list_customers():
    conn = get_db()
    rows = conn.execute("SELECT * FROM Customers ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/customers/<int:customer_id>", methods=["DELETE"])
def delete_customer_account(customer_id):
    conn = get_db()
    conn.execute("DELETE FROM Customers WHERE id = ?", (customer_id,))
    conn.commit()
    conn.close()
    return get_all_customers()


@app.route("/customers/<int:customer_id>/tags/<int:tag_id>", methods=["DELETE"])
def delete_customer_profile_tag(customer_id, tag_id):
    conn = get_db()
    conn.execute("DELETE FROM PreferenceTags WHERE id = ? AND customer_id = ?", (tag_id, customer_id))
    conn.commit()

    customer = conn.execute("SELECT * FROM Customers WHERE id = ?", (customer_id,)).fetchone()
    preferences = conn.execute("SELECT * FROM Preferences WHERE customer_id = ?", (customer_id,)).fetchall()
    tags = conn.execute("SELECT * FROM PreferenceTags WHERE customer_id = ?", (customer_id,)).fetchall()
    conn.close()

    if not customer:
        return f"<div class='error'>Customer #{customer_id} not found.</div>"

    return render_customer_profile(customer, preferences, tags)

@app.route("/api/customers/by-id", methods=["GET"])
def api_get_customer_by_id():
    customer_id = request.args.get("customer_id")
    
    if not customer_id or not str(customer_id).isdigit():
        return jsonify({"error": "Valid numeric customer_id required"}), 400

    db = get_db()
    
    customer = db.execute("SELECT * FROM Customers WHERE id = ?", (customer_id,)).fetchone()
    
    if not customer:
        db.close()
        return jsonify({"error": f"Customer #{customer_id} not found"}), 404

    profile_data = dict(customer)


    prefs = db.execute(
        "SELECT ecosystem, budget_tier, notes FROM Preferences WHERE customer_id = ?", 
        (customer_id,)
    ).fetchone()
    
    if prefs:
        profile_data.update(dict(prefs))

    tags = db.execute(
        "SELECT tag_name FROM PreferenceTags WHERE customer_id = ?", 
        (customer_id,)
    ).fetchall()
    
    profile_data["tags"] = [t["tag_name"] for t in tags]

    db.close()

    return jsonify(profile_data)

@app.route("/rag-search", methods=["POST"])
def rag_search():
    user_query = request.form.get("query", "").strip()
    if not user_query:
        return "<p class='error'>Please enter a search query.</p>", 400

    try:
        response = requests.post(
            f"{RAG_SERVER_URL}/rag/query",
            json={"query": user_query},
            timeout=125
        )
        response.raise_for_status()
        data = response.json()

    except requests.RequestException:
        data = {
            "insufficient_context": True,
            "message": "Unable to connect to the knowledge server."
        }

    return render_template("rag_result.html", data=data)

@app.route("/mcp-check-profile", methods=["POST"])
def mcp_check_profile():
    customer_id = request.form.get("customer_id")
    if not customer_id or not customer_id.isdigit():
        return "<p style='color: red;'>Please enter a valid numeric Customer ID.</p>", 400

    mcp = McpClient(host=MCP_SERVER_URL)
    
    try:
        mcp.initialize("student-2-frontend")
        
        result = mcp.call_tool("get_customer_profile", {"customer_id": int(customer_id)})
        
        if result.get("isError"):
            data = {"error": result["content"][0]["text"]}
        else:
            data = result.get("structuredContent", {})
            
    except McpError as e:
        data = {"error": str(e)}
    except Exception as e:
        data = {"error": f"Failed to connect to MCP Server: {e}"}

    template = """
    <div style="border: 1px solid #ccc; border-radius: 8px; padding: 15px; margin-top: 15px;">
        <h4>MCP Tool Result: <code>get_customer_profile</code></h4>
        
        {% if data.error %}
            <div style="color: red; background: #fee; padding: 10px; border-radius: 4px;">
                <strong>Tool Error:</strong> {{ data.error }}
            </div>
        {% else %}
            <div style="background: #f8f9fa; padding: 10px; border-radius: 4px;">
                <pre style="margin: 0; font-size: 0.9em; white-space: pre-wrap;">{{ data | tojson(indent=2) }}</pre>
            </div>
        {% endif %}
    </div>
    """
    
    return render_template_string(template, data=data)

@app.route("/staff/dashboard", methods=["GET"])
def staff_dashboard():
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Staff AI Review Dashboard</title>
        <link rel="stylesheet" href="/css/style.css">
        <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    </head>
    <body>
        <div class="app-container">
            <header class="service-header" style="display:flex; justify-content:space-between; align-items:center;">
                <h1>Staff AI Review Dashboard</h1>
                <a href="/" class="btn" style="background:#6b7280;">Back to App</a>
            </header>
            
            <div class="grid-2">
                <section class="card">
                    <h2>Pending Human Reviews</h2>
                    <button hx-get="/api/staff/workflows/pending" hx-target="#pending-list" class="btn" style="margin-bottom:15px; font-size:0.8rem;">Refresh List</button>
                    <div id="pending-list" hx-get="/api/staff/workflows/pending" hx-trigger="load, refreshPendingList from:body">
                        <p>Loading pending reviews...</p>
                    </div>
                </section>

                <section class="card">
                    <h2>Review Panel</h2>
                    <div id="review-panel" class="panel">
                        <em style="color:#6b7280;">Select a workflow from the left to review the AI's work.</em>
                    </div>
                </section>
            </div>
        </div>
    </body>
    </html>
    """
    return html

@app.route("/api/staff/workflows/pending", methods=["GET"])
def get_pending_workflows():
    try:
        resp = requests.get(f"{MULTI_AGENT_URL}/workflows?student=student-2", timeout=5)
        workflows = resp.json().get("workflows", [])
        pending = [w for w in workflows if w.get("status") == "awaiting_human"]
        
        if not pending:
            return "<p style='color:#10b981; font-weight:bold;'>Inbox Zero! No pending AI workflows.</p>"
            
        html = "<ul style='list-style:none; padding:0;'>"
        for w in pending:
            # Safely handle None values from the Multi-Agent Server
            task_str = str(w.get("task") or "No task description")[:60]
            verdict = str(w.get("reviewer_verdict") or "pending").upper()
            verdict_color = "red" if "FAIL" in verdict else "orange"
            
            html += f"""
            <li style='border:1px solid #ccc; margin-bottom:10px; padding:10px; border-radius:4px; cursor:pointer;'
                hx-get='/api/staff/workflow/{w['id']}' hx-target='#review-panel'>
                <strong>{w['id']}</strong>
                <p style='font-size:0.85rem; margin:5px 0;'><strong>Task:</strong> {task_str}...</p>
                <p style='font-size:0.8rem; color:#666;'>
                    Reviewer Verdict: <span style='color:{verdict_color}; font-weight:bold;'>{verdict}</span>
                </p>
            </li>
            """
        html += "</ul>"
        return html
    except Exception as e:
        return f"<div class='error'>Failed to connect: {str(e)}</div>"

@app.route("/api/staff/workflow/<workflow_id>", methods=["GET"])
def get_workflow_details(workflow_id):
    try:
        resp = requests.get(f"{MULTI_AGENT_URL}/workflow/{workflow_id}", timeout=5)
        if resp.status_code == 404:
            return "<div class='error'>Workflow not found.</div>", 404
        
        wf = resp.json()
        work_ans = wf.get("work", {}).get("answer", "")
        review = wf.get("review", {})
        risks_html = "".join([f"<li>{r}</li>" for r in review.get("risks", [])])
        
        html = f"""
        <div style='margin-bottom:15px;'>
            <h4>Workflow: {wf['id']}</h4>
            <p><strong>Task:</strong> {wf['task']}</p>
        </div>
        
        <div style='margin-bottom:15px;'>
            <h5>1. AI Worker's Proposed Answer:</h5>
            <pre style='background:#f9fafb; padding:10px; border:1px solid #ddd; white-space:pre-wrap; font-size:0.85rem;'>{work_ans}</pre>
        </div>

        <div style='margin-bottom:20px; background:#fff3cd; padding:10px; border:1px solid #ffeeba; border-radius:4px;'>
            <h5>2. AI Reviewer's Analysis:</h5>
            <p><strong>Verdict:</strong> {str(review.get('verdict')).upper()}</p>
            <p><strong>Summary:</strong> {review.get('summary', '')}</p>
            {"<p><strong>Risks:</strong></p><ul style='margin-top:5px; font-size:0.85rem;'>" + risks_html + "</ul>" if risks_html else ""}
        </div>

        <h5>3. Human Decision</h5>
        <form hx-post='/api/staff/workflow/{wf['id']}/decision' hx-target='#review-panel'>
            <div style='margin-bottom:10px;'>
                <label><strong>Action:</strong></label><br>
                <select name='decision' required style='width:100%; padding:5px;' onchange="document.getElementById('note-req').innerText = (this.value === 'reject' || this.value === 'partial' || this.value === 'correct') ? '*' : '';">
                    <option value=''>-- Select Decision --</option>
                    <option value='approve'>Approve (Use AI's exact answer)</option>
                    <option value='correct'>Correct (Provide manual fix below)</option>
                    <option value='partial'>Partial (Accept with a note)</option>
                    <option value='reject'>Reject (Discard AI answer)</option>
                </select>
            </div>
            <div style='margin-bottom:10px;'>
                <label><strong>Note / Reasoning <span id='note-req' style='color:red;'></span>:</strong></label><br>
                <input type='text' name='note' style='width:100%; padding:5px;' placeholder='Required for partial/reject'>
            </div>
            <div style='margin-bottom:15px;'>
                <label><strong>Corrected Answer:</strong></label><br>
                <textarea name='corrected_answer' style='width:100%; padding:5px;' rows='3' placeholder='Required if decision is Correct'></textarea>
            </div>
            <button type='submit' class='btn' style='width:100%; background:#2563eb;'>Submit Decision</button>
        </form>
        """
        return html
    except Exception as e:
        return f"<div class='error'>Failed to fetch workflow: {str(e)}</div>"

@app.route("/api/staff/workflow/<workflow_id>/decision", methods=["POST"])
def submit_workflow_decision(workflow_id):
    decision = request.form.get("decision")
    
    payload = {
        "decision": decision,
        "reviewer": "Staff Dashboard User",
        "note": request.form.get("note", "").strip(),
        "corrected_answer": request.form.get("corrected_answer", "").strip()
    }
    
    try:
        resp = requests.post(f"{MULTI_AGENT_URL}/workflow/{workflow_id}/decision", json=payload, timeout=10)
        if resp.status_code == 200:
            response = app.make_response(f"<div class='panel' style='border-left:4px solid #10b981;'><strong>Success:</strong> Recorded '{decision}' for {workflow_id}</div>")
            response.headers["HX-Trigger"] = "refreshPendingList, refreshCustomers"
            return response
        return f"<div class='error'>Error: {resp.json().get('error')}</div>"
    except Exception as e:
        return f"<div class='error'>Server error: {str(e)}</div>"

def render_customer_profile(customer, preferences, tags):
    html = f"<h3>#{customer['id']} - {customer['first_name']} {customer['last_name']}</h3>"
    html += f"<p style='font-size:0.9rem;'><strong>Email:</strong> {customer['email']} | <strong>Phone:</strong> {customer['phone']}</p>"
    html += f"<p style='font-size:0.9rem;'><strong>Shipping:</strong> {customer['shipping_street']}, {customer['shipping_city']} {customer['shipping_state']} {customer['shipping_postcode']}</p>"
    
    html += "<h4 style='margin-top:0.75rem;'>Ecosystem Preferences:</h4><ul style='padding-left:1.2rem; font-size:0.9rem;'>"
    for p in preferences:
        html += f"<li><strong>{p['ecosystem']}</strong> ({p['budget_tier']}): {p['notes']}</li>"
    html += "</ul>"

    html += "<h4 style='margin-top:0.75rem;'>Profile Preference Tags:</h4><p style='margin-top:0.25rem;'>"
    if not tags:
        html += "<em style='font-size:0.85rem; color:#6b7280;'>No preference tags assigned to this profile.</em>"
    else:
        for t in tags:
            badge_cls = "badge" if t['source'] == 'ai_agent' else "badge badge-cream"
            html += f"""
            <span class='{badge_cls}' style='margin-right:6px; display:inline-flex; align-items:center; gap:6px; padding:0.2rem 0.5rem;'>
                {t['tag_name']}
                <button style='background:none; border:none; color:inherit; cursor:pointer; font-weight:bold; font-size:1rem; line-height:1; padding:0;'
                        hx-delete='/customers/{customer['id']}/tags/{t['id']}'
                        hx-target='#student-result'
                        hx-confirm='Remove tag "{t['tag_name']}" from Customer #{customer['id']}?'>&times;</button>
            </span>"""
    html += "</p>"
    return html

def render_workflow_status(workflow, cid):
    status = workflow.get("status")
    wid = workflow.get("id")

    html = f"<div class='ai-response panel' id='wf-container-{wid}'>"
    html += f"<h4>Workflow: {wid}</h4>"
    html += f"<p><strong>Status:</strong> <span class='badge'>{status}</span></p>"

    if status == "awaiting_human":
        review = workflow.get("review", {})
        html += "<div class='alert alert-warning' style='margin-top: 10px;'>"
        html += "<p>The AI Worker has drafted an answer. Waiting for human approval in the Staff Terminal.</p>"
        html += f"<p><em>Reviewer Verdict: {review.get('verdict')}</em></p>"
        html += f"<button hx-get='/api/agent/status/{wid}?customer_id={cid}' hx-target='#wf-container-{wid}' hx-swap='outerHTML' class='btn' style='margin-top: 10px;'>Refresh Status</button>"
        html += "</div>"

    elif status in ["approved", "corrected", "partially_accepted"]:
        ans = workflow.get("final_answer", "")
        tags_str = ""
        try:
            data = json.loads(ans)
            if isinstance(data, dict) and "recommended_tags" in data:
                tags_str = ",".join(data["recommended_tags"])
                reasoning = data.get("reasoning", "")
                
                html += "<div class='alert alert-success'>"
                html += "<p><strong>Suggested Preference Tags:</strong></p><p>"
                for tag in data["recommended_tags"]:
                    html += f"<span class='badge' style='margin-right:4px;'>{tag}</span>"
                html += f"</p><p><em><strong>Reasoning:</strong> {reasoning}</em></p>"
                html += "</div>"
        except json.JSONDecodeError:
            html += f"<div class='alert alert-success'><pre>{ans}</pre></div>"

        if tags_str:
            html += f"""
            <form hx-post='/apply-tags' hx-target='#context-result' style='margin-top:0.85rem;'>
                <input type='hidden' name='customer_id' value='{cid}'>
                <input type='hidden' name='tags' value='{tags_str}'>
                <button type='submit' class='btn' style='width:100%;'>Apply Suggestions to Profile</button>
            </form>
            """

    elif status == "rejected":
        html += "<div class='alert alert-danger'>"
        html += "<strong>Workflow Rejected by Human Reviewer</strong>"
        html += f"<p>Note: {workflow.get('human', {}).get('note')}</p>"
        html += "</div>"

    elif status == "failed":
        err = workflow.get("error", "An unknown error occurred in the AI server.")
        html += f"<div class='alert alert-danger'><strong>AI Workflow Failed:</strong> {err}</div>"
    
    else:
        html += "<p>Processing workflow...</p>"

    html += "</div>"
    return html


with app.app_context():
    init_db()
    seed_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    is_debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="127.0.0.1", port=port, debug=is_debug)