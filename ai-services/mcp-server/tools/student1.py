from registry import ToolError, service_get, tool

SERVICE = "student-1"


@tool(
    name="get_catalog_product",
    description="Get one OmniTech catalogue product by id: name, brand, category, price, stock and description.",
    properties={"product_id": {"type": "integer", "minimum": 1, "description": "Catalogue product id, e.g. 1"}},
    required=["product_id"],
    example={"product_id": 1},
)
def get_catalog_product(product_id):
    product = service_get(SERVICE, f"/api/products/{product_id}")
    if product is None:
        raise ToolError(f"Product #{product_id} not found")
    return {
        "product_id": product["id"],
        "name": product["name"],
        "brand": product["brand"],
        "category": product.get("category_name"),
        "price": product["price"],
        "stock": product["stock"],
        "description": product.get("description") or "",
    }


@tool(
    name="get_catalog_specifications",
    description="Get the technical specifications recorded for one catalogue product (capacity, energy rating, etc.).",
    properties={"product_id": {"type": "integer", "minimum": 1, "description": "Catalogue product id, e.g. 1"}},
    required=["product_id"],
    example={"product_id": 1},
)
def get_catalog_specifications(product_id):
    product = service_get(SERVICE, f"/api/products/{product_id}")
    if product is None:
        raise ToolError(f"Product #{product_id} not found")
    specs = service_get(SERVICE, f"/api/products/{product_id}/specifications") or []
    return {
        "product_id": product_id,
        "product_name": product["name"],
        "spec_count": len(specs),
        "specifications": [
            {"name": s["spec_name"], "value": s["spec_value"]} for s in specs
        ],
    }


@tool(
    name="list_catalog_categories",
    description="List every product category in the OmniTech catalogue with its description.",
    example={},
)
def list_catalog_categories():
    categories = service_get(SERVICE, "/api/categories")
    if categories is None:
        raise ToolError("Student 1 API has no /api/categories endpoint")
    return {
        "count": len(categories),
        "categories": [
            {"id": c["id"], "name": c["name"], "description": c.get("description") or ""}
            for c in categories
        ],
    }
