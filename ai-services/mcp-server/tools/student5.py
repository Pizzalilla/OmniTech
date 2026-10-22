"""
Student 5 - AI Warranty Evaluating tools.

All tools are read-only: they call Student 5's REST API (port 5005) with GET.
"""

from registry import ToolError, service_get, tool

SERVICE = "student-5"

# TOOL: a consultation session's saved product recommendations
@tool(
    name="get_warranty_product",
    description="Get product information relevant to an OmniTech warranty claim, including name, category, price, description and warranty period.",
    properties={
        "product_id": {
            "type": "integer",
            "minimum": 1,
            "description": "Product id, e.g. 1"
        }
    },
    required=["product_id"],
    example={"product_id": 1},
)
def get_warranty_product(product_id):
    product = service_get(SERVICE, f"/api/products/{product_id}")
    if product is None:
        raise ToolError(f"Product #{product_id} not found")
    
    return {
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "product_category": product["product_category"],
        "product_price": product["product_price"],
        "product_description": product["product_description"],
        "product_warranty_years": product["product_warranty_years"],
    }