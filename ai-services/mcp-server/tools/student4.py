"""
Student 4 - Cart & Order Processing tools.

All tools are read-only: they call Student 4's REST API (port 5004) with GET.
"""

from registry import ToolError, service_get, tool

SERVICE = "student-4"


# TOOL: one order's status and line items
@tool(
    name="get_order_status",
    description="Get the status, total and line items of one order by its order number.",
    properties={"order_id": {"type": "integer", "minimum": 1, "description": "Order number, e.g. 5"}},
    required=["order_id"],
    example={"order_id": 1},
)
def get_order_status(order_id):
    order = service_get(SERVICE, f"/api/orders/{order_id}")
    if order is None:
        raise ToolError(f"Order #{order_id} not found")
    items = order.get("line_items", [])
    return {
        "order_id": order["order_id"],
        "status": order["fulfillment_status"],
        "total_price": order["total_price"],
        "created_at": order.get("created_at"),
        "item_count": sum(i["quantity"] for i in items),
        "items": [{"product_name": i["product_name"], "quantity": i["quantity"], "unit_price": i["unit_price"]}
                  for i in items],
    }


# TOOL: the customer's current shopping cart
@tool(
    name="get_cart",
    description="Get the customer's current shopping cart: items, stock, fulfilment option and totals.",
    example={},
)
def get_cart():
    cart = service_get(SERVICE, "/api/cart")
    if cart is None:
        raise ToolError("Student 4 API has no /api/cart endpoint (needs the Release 1 Student 4 service)")
    return cart


# TOOL: real appliance specs for grounding AI answers
@tool(
    name="get_product_specs",
    description="Get appliance specs (power draw, plug, size, weight, clearances, energy rating) for product ids.",
    properties={"product_ids": {"type": "array", "items": {"type": "integer", "minimum": 1},
                                "minItems": 1, "maxItems": 20, "description": "Product ids, e.g. [511, 512]"}},
    required=["product_ids"],
    example={"product_ids": [511, 512]},
)
def get_product_specs(product_ids):
    ids = ",".join(str(i) for i in product_ids)
    data = service_get(SERVICE, "/api/products/specs", params={"ids": ids})
    if data is None:
        raise ToolError("Student 4 API has no /api/products/specs endpoint (needs the Release 1 Student 4 service)")
    return data
