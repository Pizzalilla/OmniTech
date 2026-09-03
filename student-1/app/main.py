import os

from db import (
    create_category,
    delete_category,
    get_category,
    init_db,
    list_categories,
    update_category,
)
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from sqlite3 import IntegrityError

load_dotenv()
init_db()  # create tables + seed if the DB is empty

app = Flask(__name__, template_folder="../templates", static_folder="../static")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "product-catalog"})


@app.route("/")
def index():
    return render_template("index.html", service_name="Product Catalog")


# GET = list all categories, POST = add a new one
@app.route("/api/categories", methods=["GET", "POST"])
def api_categories():
    if request.method == "GET":
        return jsonify(list_categories())

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    try:
        category = create_category(name, data.get("description"))
    except IntegrityError:
        return jsonify({"error": "category name already exists"}), 409
    return jsonify(category), 201


# GET one, PUT to edit, DELETE to remove
@app.route("/api/categories/<int:category_id>", methods=["GET", "PUT", "DELETE"])
def api_category(category_id):
    category = get_category(category_id)
    if category is None:
        return jsonify({"error": "category not found"}), 404

    if request.method == "GET":
        return jsonify(category)

    if request.method == "DELETE":
        try:
            delete_category(category_id)
        except IntegrityError:
            # refuse to delete if category still has products
            return jsonify({"error": "category still has products"}), 409
        return "", 204

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    try:
        updated = update_category(category_id, name, data.get("description"))
    except IntegrityError:
        return jsonify({"error": "category name already exists"}), 409
    return jsonify(updated)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
