import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import agent
from backend.ai import AIUnavailable, summarise_product
from database.db import (
    create_category,
    create_product,
    create_specification,
    delete_category,
    delete_product,
    delete_specification,
    get_category,
    get_product,
    get_specification,
    list_brands,
    list_categories,
    list_products,
    list_specifications,
    update_category,
    update_product,
    update_specification,
)
from database.init_db import init_db
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, render_template, request
from sqlite3 import IntegrityError

load_dotenv()
init_db()

# the agentic loop logs each stage here, so it shows up in docker compose logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

app = Flask(
    __name__,
    template_folder=str(ROOT / "frontend" / "templates"),
    static_folder=str(ROOT / "frontend" / "static"),
)

# the unified home page
HOME_URL = os.getenv("HOME_URL", "http://localhost:8080")


@app.context_processor
def inject_home_url():
    return {"home_url": HOME_URL}


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "product-catalog"})


def _filters_from_request() -> dict:
    return {
        "category_id": request.args.get("category_id", type=int),
        "brand": request.args.get("brand") or None,
        "min_price": request.args.get("min_price", type=float),
        "max_price": request.args.get("max_price", type=float),
        "search": (request.args.get("search") or "").strip() or None,
        "spec_keyword": (request.args.get("spec_keyword") or "").strip() or None,
    }


@app.route("/")
def catalog():
    return render_template(
        "catalog.html",
        products=list_products(),
        categories=list_categories(),
        brands=list_brands(),
    )


# htmx swaps this fragment into the page whenever a filter changes
@app.route("/products/grid")
def product_grid():
    return render_template(
        "partials/product_grid.html",
        products=list_products(**_filters_from_request()),
    )


@app.route("/products/<int:product_id>")
def product_detail(product_id):
    product = get_product(product_id)
    if product is None:
        abort(404)

    return render_template(
        "product_detail.html",
        product=product,
        specifications=list_specifications(product_id),
    )


@app.route("/products/<int:product_id>/ai-review", methods=["POST"])
def product_ai_review(product_id):
    product = get_product(product_id)
    if product is None:
        abort(404)

    try:
        result = agent.run(product, list_specifications(product_id))
    except AIUnavailable as exc:
        # htmx ignores the body of an error response, so the failure is
        # rendered as a normal 200 fragment instead
        return render_template("partials/ai_review.html", error=str(exc))

    return render_template("partials/ai_review.html", result=result)


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


@app.route("/api/products", methods=["GET", "POST"])
def api_products():
    if request.method == "GET":
        return jsonify(list_products(**_filters_from_request()))

    data = request.get_json(silent=True) or {}
    error, values = _parse_product_payload(data)
    if error:
        return jsonify(error), 400

    try:
        product = create_product(*values)
    except IntegrityError:
        return jsonify({"error": "invalid category_id"}), 400
    return jsonify(product), 201


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


def _parse_spec_payload(data: dict) -> tuple[dict | None, tuple | None]:
    spec_name = (data.get("spec_name") or "").strip()
    spec_value = (data.get("spec_value") or "").strip()
    if not spec_name or not spec_value:
        return {"error": "spec_name and spec_value are required"}, None
    return None, (spec_name, spec_value)


@app.route("/api/products/<int:product_id>/specifications", methods=["GET", "POST"])
def api_specifications(product_id):
    if get_product(product_id) is None:
        return jsonify({"error": "product not found"}), 404

    if request.method == "GET":
        return jsonify(list_specifications(product_id))

    data = request.get_json(silent=True) or {}
    error, values = _parse_spec_payload(data)
    if error:
        return jsonify(error), 400

    return jsonify(create_specification(product_id, *values)), 201


@app.route(
    "/api/products/<int:product_id>/specifications/<int:spec_id>",
    methods=["GET", "PUT", "DELETE"],
)
def api_specification(product_id, spec_id):
    spec = get_specification(spec_id)
    # reject a spec id that belongs to a different product
    if spec is None or spec["product_id"] != product_id:
        return jsonify({"error": "specification not found"}), 404

    if request.method == "GET":
        return jsonify(spec)

    if request.method == "DELETE":
        delete_specification(spec_id)
        return "", 204

    data = request.get_json(silent=True) or {}
    error, values = _parse_spec_payload(data)
    if error:
        return jsonify(error), 400

    return jsonify(update_specification(spec_id, *values))


@app.route("/api/products/<int:product_id>/ai-summary", methods=["POST"])
def api_product_ai_summary(product_id):
    product = get_product(product_id)
    if product is None:
        return jsonify({"error": "product not found"}), 404

    try:
        result = summarise_product(product, list_specifications(product_id))
    except AIUnavailable as exc:
        return jsonify({"error": "ai summary unavailable", "detail": str(exc)}), 503

    return jsonify(result)


@app.route("/api/products/<int:product_id>/ai-review", methods=["POST"])
def api_product_ai_review(product_id):
    product = get_product(product_id)
    if product is None:
        return jsonify({"error": "product not found"}), 404

    try:
        result = agent.run(product, list_specifications(product_id))
    except AIUnavailable as exc:
        return jsonify({"error": "ai review unavailable", "detail": str(exc)}), 503

    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
