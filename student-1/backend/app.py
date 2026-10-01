import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests
from backend import agent
from backend import rag_client
from backend.ai import AIUnavailable, summarise_product
from backend.mcp_client import McpClient, McpError
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

# shared local MCP / RAG servers
MCP_ENABLED = os.getenv("MCP_ENABLED", "true").lower() == "true"
MCP_HOST = os.getenv("MCP_HOST", "http://localhost:6003")
MCP_TIMEOUT = int(os.getenv("MCP_TIMEOUT", "30"))
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() == "true"


@app.context_processor
def inject_home_url():
    return {"home_url": HOME_URL}


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "product-catalog"})


def _filters_from_request() -> dict:
    return {
        "category_id": request.args.get("category_id", type=int),
        "brands": [value for value in request.args.getlist("brand") if value],
        "min_price": request.args.get("min_price", type=float),
        "max_price": request.args.get("max_price", type=float),
        "search": (request.args.get("search") or "").strip() or None,
        "spec_keyword": (request.args.get("spec_keyword") or "").strip() or None,
    }


@app.route("/")
def catalog():
    products = list_products()
    prices = [float(product["price"]) for product in products]
    ceiling = max(prices) if prices else 2000
    slider_max = max(2000, int((ceiling + 99) // 100 * 100))
    return render_template(
        "catalog.html",
        products=products,
        categories=list_categories(),
        brands=list_brands(),
        slider_max=slider_max,
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
        # htmx ignores the body of an error response, so the failure will be rendered as a normal 200 fragment instead
        return render_template("partials/ai_review.html", error=str(exc))

    return render_template("partials/ai_review.html", result=result)


def _parse_product_id_from_request():
    if "product_id" in request.form:
        return int(request.form.get("product_id"))
    if request.is_json:
        return int((request.get_json(silent=True) or {}).get("product_id"))
    raise ValueError("missing product_id")


def _wants_json():
    # HTMX and normal browser forms get HTML; only JSON API clients get JSON
    if request.headers.get("HX-Request", "").lower() == "true":
        return False
    if request.form:
        return False
    return bool(request.is_json)


def _mcp_fragment(tool_name, arguments, status, error=None, data=None, raw=None):
    return render_template(
        "partials/mcp_result.html",
        tool_name=tool_name,
        arguments=arguments,
        status=status,
        error=error,
        data=data,
        raw=raw,
    )


def _call_mcp_tool(tool_name, arguments):
    """Ask the shared MCP server to run one of our tools."""
    want_json = _wants_json()

    if not MCP_ENABLED:
        if want_json:
            return jsonify({"error": "MCP is disabled (MCP_ENABLED=false)."}), 200
        return _mcp_fragment(
            tool_name, arguments, "error", error="MCP is disabled (MCP_ENABLED=false)."
        )

    try:
        result = McpClient(MCP_HOST, timeout=MCP_TIMEOUT).call_tool(tool_name, arguments)
    except McpError as exc:
        if want_json:
            return jsonify({"error": f"MCP server rejected the call: {exc}"}), 200
        return _mcp_fragment(
            tool_name, arguments, "error", error=f"MCP server rejected the call: {exc}"
        )
    except requests.RequestException:
        message = (
            f"MCP server offline at {MCP_HOST}. "
            "Start it with python server.py in ai-services/mcp-server."
        )
        if want_json:
            return jsonify({"error": message}), 200
        return _mcp_fragment(tool_name, arguments, "error", error=message)

    if want_json:
        return jsonify(result)

    raw = json.dumps(result, indent=2)
    if result.get("isError"):
        message = result["content"][0]["text"] if result.get("content") else "Tool returned an error"
        return _mcp_fragment(tool_name, arguments, "warning", error=message, raw=raw)

    return _mcp_fragment(
        tool_name, arguments, "success", data=result.get("structuredContent"), raw=raw
    )


@app.route("/api/mcp/catalog-product", methods=["POST"])
def mcp_catalog_product():
    try:
        product_id = _parse_product_id_from_request()
    except (TypeError, ValueError):
        if _wants_json():
            return jsonify({"error": "product_id is required"}), 400
        return _mcp_fragment("get_catalog_product", {}, "error", error="Please enter a valid product id.")
    return _call_mcp_tool("get_catalog_product", {"product_id": product_id})


@app.route("/api/mcp/catalog-specifications", methods=["POST"])
def mcp_catalog_specifications():
    try:
        product_id = _parse_product_id_from_request()
    except (TypeError, ValueError):
        if _wants_json():
            return jsonify({"error": "product_id is required"}), 400
        return _mcp_fragment(
            "get_catalog_specifications", {}, "error", error="Please enter a valid product id."
        )
    return _call_mcp_tool("get_catalog_specifications", {"product_id": product_id})


@app.route("/api/rag/query", methods=["POST"])
def rag_query():
    """Forward a question to the shared RAG server."""
    if request.is_json:
        query_text = ((request.get_json(silent=True) or {}).get("query") or "").strip()
    else:
        query_text = (request.form.get("query") or "").strip()
    if not query_text:
        if _wants_json():
            return jsonify({"error": "query is required"}), 400
        return render_template(
            "partials/rag_result.html",
            result={"error": "Please enter a question."},
        )

    if not RAG_ENABLED:
        result = {"error": "RAG is disabled (RAG_ENABLED=false)."}
    else:
        try:
            result = rag_client.ask(query_text)
        except requests.RequestException:
            result = {"error": "The shared RAG server is not reachable right now."}

    if _wants_json():
        return jsonify(result)
    return render_template("partials/rag_result.html", result=result)


@app.route("/admin")
def admin():
    return render_template(
        "admin.html",
        products=list_products(),
        categories=list_categories(),
        form={},
    )


def _category_fragment(editing_id=None, error=None, values=None):
    return render_template(
        "partials/category_table.html",
        categories=list_categories(),
        editing_id=editing_id,
        error=error,
        values=values,
    )


def _form_value(field: str) -> str:
    return (request.form.get(field) or "").strip()


@app.route("/admin/categories", methods=["GET", "POST"])
def admin_categories():
    if request.method == "GET":
        return _category_fragment()

    name = _form_value("name")
    if not name:
        return _category_fragment(error="name is required", values=request.form)

    try:
        create_category(name, _form_value("description") or None)
    except IntegrityError:
        return _category_fragment(
            error=f"a category named {name} already exists", values=request.form
        )

    return _category_fragment()


@app.route("/admin/categories/<int:category_id>/edit")
def admin_category_edit(category_id):
    if get_category(category_id) is None:
        abort(404)

    return _category_fragment(editing_id=category_id)


@app.route("/admin/categories/<int:category_id>", methods=["PUT", "DELETE"])
def admin_category(category_id):
    category = get_category(category_id)
    if category is None:
        abort(404)

    if request.method == "DELETE":
        try:
            delete_category(category_id)
        except IntegrityError:
            return _category_fragment(
                error=f"{category['name']} still has products, so it cannot be deleted"
            )
        return _category_fragment()

    name = _form_value("name")
    if not name:
        return _category_fragment(editing_id=category_id, error="name is required")

    try:
        update_category(category_id, name, _form_value("description") or None)
    except IntegrityError:
        return _category_fragment(
            editing_id=category_id, error=f"a category named {name} already exists"
        )

    return _category_fragment()


def _product_fragment(editing_id=None, error=None, form=None):
    return render_template(
        "partials/product_table.html",
        products=list_products(),
        categories=list_categories(),
        editing_id=editing_id,
        error=error,
        form=form or {},
    )


@app.route("/admin/products", methods=["GET", "POST"])
def admin_products():
    if request.method == "GET":
        return _product_fragment()

    error, values = _parse_product_payload(request.form)
    if error:
        return _product_fragment(error=error["error"], form=request.form)

    try:
        create_product(*values)
    except IntegrityError:
        return _product_fragment(error="that category no longer exists", form=request.form)

    return _product_fragment()


@app.route("/admin/products/<int:product_id>/edit")
def admin_product_edit(product_id):
    product = get_product(product_id)
    if product is None:
        abort(404)

    return _product_fragment(editing_id=product_id, form=product)


@app.route("/admin/products/<int:product_id>", methods=["PUT", "DELETE"])
def admin_product(product_id):
    if get_product(product_id) is None:
        abort(404)

    if request.method == "DELETE":
        delete_product(product_id)
        return _product_fragment()

    error, values = _parse_product_payload(request.form)
    if error:
        return _product_fragment(
            editing_id=product_id, error=error["error"], form=request.form
        )

    try:
        update_product(product_id, *values)
    except IntegrityError:
        return _product_fragment(
            editing_id=product_id, error="that category no longer exists", form=request.form
        )

    return _product_fragment()


def _specification_fragment(product, editing_id=None, error=None, values=None):
    return render_template(
        "partials/specification_table.html",
        product=product,
        specifications=list_specifications(product["id"]),
        editing_id=editing_id,
        error=error,
        values=values,
    )


def _owned_specification(product_id, spec_id):
    spec = get_specification(spec_id)
    # a spec id belonging to another product must not be editable from this page
    if spec is None or spec["product_id"] != product_id:
        return None
    return spec


@app.route("/admin/products/<int:product_id>/specifications")
def admin_product_specifications(product_id):
    product = get_product(product_id)
    if product is None:
        abort(404)

    return render_template(
        "admin_specifications.html",
        product=product,
        specifications=list_specifications(product_id),
    )


@app.route("/admin/products/<int:product_id>/specifications/rows")
def admin_specification_rows(product_id):
    product = get_product(product_id)
    if product is None:
        abort(404)

    return _specification_fragment(product)


@app.route("/admin/products/<int:product_id>/specifications", methods=["POST"])
def admin_specifications(product_id):
    product = get_product(product_id)
    if product is None:
        abort(404)

    error, values = _parse_spec_payload(request.form)
    if error:
        return _specification_fragment(
            product, error=error["error"], values=request.form
        )

    create_specification(product_id, *values)
    return _specification_fragment(product)


@app.route("/admin/products/<int:product_id>/specifications/<int:spec_id>/edit")
def admin_specification_edit(product_id, spec_id):
    product = get_product(product_id)
    if product is None or _owned_specification(product_id, spec_id) is None:
        abort(404)

    return _specification_fragment(product, editing_id=spec_id)


@app.route(
    "/admin/products/<int:product_id>/specifications/<int:spec_id>",
    methods=["PUT", "DELETE"],
)
def admin_specification(product_id, spec_id):
    product = get_product(product_id)
    if product is None or _owned_specification(product_id, spec_id) is None:
        abort(404)

    if request.method == "DELETE":
        delete_specification(spec_id)
        return _specification_fragment(product)

    error, values = _parse_spec_payload(request.form)
    if error:
        return _specification_fragment(
            product, editing_id=spec_id, error=error["error"]
        )

    update_specification(spec_id, *values)
    return _specification_fragment(product)


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
    app.run(host="0.0.0.0", port=5000, debug=os.getenv("FLASK_DEBUG") == "1")
