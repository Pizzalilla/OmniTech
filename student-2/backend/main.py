import os
import sys
from flask import Flask, abort, jsonify, render_template, request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

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


@app.route("/customers/<int:customer_id>", methods=["DELETE"])
def delete_customer_account(customer_id):
    conn = get_db()
    conn.execute("DELETE FROM Customers WHERE id = ?", (customer_id,))
    conn.commit()
    conn.close()
    return get_all_customers()


@app.route("/generate-ai-suggestions", methods=["POST"])
def generate_ai_suggestions():
    cid = request.form.get("customer_id", "").strip()
    if not cid:
        return "<div class='error'>Please enter a customer ID.</div>"

    conn = get_db()
    customer = conn.execute("SELECT * FROM Customers WHERE id = ?", (cid,)).fetchone()
    if not customer:
        conn.close()
        return f"<div class='error'>Customer #{cid} not found.</div>"

    preferences = conn.execute("SELECT * FROM Preferences WHERE customer_id = ?", (cid,)).fetchall()
    conn.close()
    
    res = agent.generate_user_tags(dict(customer), [dict(p) for p in preferences])
    recommended_tags = res.get("recommended_tags", [])
    tags_str = ",".join(recommended_tags)

    html = "<div class='ai-response'>"
    html += f"<h4>{customer['first_name']} {customer['last_name']}</h4>"
    html += "<p><strong>Suggested Preference Tags:</strong></p>"
    for tag in recommended_tags:
        html += f"<span class='badge' style='margin-right:4px;'>{tag}</span>"
    html += f"<p><em><strong>Reasoning:</strong> {res.get('reasoning')}</em></p>"
    
    html += f"""
    <form hx-post='/apply-tags' hx-target='#context-result' style='margin-top:0.85rem;'>
        <input type='hidden' name='customer_id' value='{cid}'>
        <input type='hidden' name='tags' value='{tags_str}'>
        <button type='submit' class='btn' style='width:100%;'>Apply Suggestions to Profile</button>
    </form>
    """
    html += "</div>"
    return html


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
        except Exception:
            pass

    conn.commit()
    updated_tags = conn.execute("SELECT * FROM PreferenceTags WHERE customer_id = ?", (cid,)).fetchall()
    conn.close()

    html = "<div class='panel'>"
    html += "<h4>Successfully Applied Suggestions</h4>"
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


@app.route("/api/customers/<int:customer_id>", methods=["DELETE"])
def api_delete_customer(customer_id):
    conn = get_db()
    conn.execute("DELETE FROM Customers WHERE id = ?", (customer_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Account deleted"})


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


with app.app_context():
    init_db()
    seed_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)