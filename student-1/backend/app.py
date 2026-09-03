import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.db import (
    create_category,
    create_product,
    delete_category,
    delete_product,
    get_category,
    get_product,
    list_categories,
    list_products,
    update_category,
    update_product,
)
from database.init_db import init_db
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from sqlite3 import IntegrityError

load_dotenv()
init_db()  # create tables + seed if the DB is empty

app = Flask(
    __name__,
    template_folder=str(ROOT / "frontend" / "templates"),
    static_folder=str(ROOT / "frontend" / "static"),
)

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


def _parse_product_payload(data: dict) -> tuple[dict | None, tuple | None]:
    """Validate product JSON. Returns (error_response, values) where one is None."""
    name = (data.get("name") or "").strip()
    brand = (data.get("brand") or "").strip()
    if not name or not brand:
        return {"error": "name and brand are required"}, None

    try:
        category_id = int(data["category_id"])
        price = float(data["price"])
        stock = int(data.get("stock", 0))
    except (KeyError, TypeError, ValueError):
        return {"error": "category_id, price, and stock must be valid numbers"}, None

    if price < 0 or stock < 0:
        return {"error": "price and stock cannot be negative"}, None

    if get_category(category_id) is None:
        return {"error": "category not found"}, None

    values = (
        name,
        brand,
        category_id,
        price,
        stock,
        data.get("description"),
        data.get("image_url"),
    )
    return None, values


# GET = list/filter products, POST = add a product
@app.route("/api/products", methods=["GET", "POST"])
def api_products():
    if request.method == "GET":
        category_id = request.args.get("category_id", type=int)
        brand = request.args.get("brand")
        min_price = request.args.get("min_price", type=float)
        max_price = request.args.get("max_price", type=float)
        return jsonify(
            list_products(
                category_id=category_id,
                brand=brand,
                min_price=min_price,
                max_price=max_price,
            )
        )

    data = request.get_json(silent=True) or {}
    error, values = _parse_product_payload(data)
    if error:
        return jsonify(error), 400

    try:
        product = create_product(*values)
    except IntegrityError:
        return jsonify({"error": "invalid category_id"}), 400
    return jsonify(product), 201


# GET one, PUT to edit, DELETE to remove
@app.route("/api/products/<int:product_id>", methods=["GET", "PUT", "DELETE"])
def api_product(product_id):
    product = get_product(product_id)
    if product is None:
        return jsonify({"error": "product not found"}), 404

    if request.method == "GET":
        return jsonify(product)

    if request.method == "DELETE":
        delete_product(product_id)
        return "", 204

    data = request.get_json(silent=True) or {}
    error, values = _parse_product_payload(data)
    if error:
        return jsonify(error), 400

    try:
        updated = update_product(product_id, *values)
    except IntegrityError:
        return jsonify({"error": "invalid category_id"}), 400
    return jsonify(updated)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
