"""
TEMPLATE - copy this file to tools/studentN.py (no leading underscore) to add
your own tools. Files starting with _ are not loaded.

Rules (the tool boundary):
  * Tools are READ-ONLY. Get data only through service_get(), which does a GET
    on your own service's REST API. Never open another student's database.
  * Give every input a type in `properties`; the server rejects bad inputs
    before your function runs.
  * Raise ToolError("message") when the tool can't do its job (e.g. not found);
    the caller gets it back as an error result instead of a crash.
  * Add an `example` - validate.py uses it to call your tool.
"""

from registry import ToolError, service_get, tool

SERVICE = "student-N"   # student-1 ... student-5 (see SERVICES in registry.py)


# TOOL: short comment saying what it does
@tool(
    name="get_something",
    description="One sentence an AI (or a teammate) can read to know when to use this tool.",
    properties={"item_id": {"type": "integer", "minimum": 1, "description": "Which item"}},
    required=["item_id"],
    example={"item_id": 1},
)
def get_something(item_id):
    data = service_get(SERVICE, f"/api/items/{item_id}")
    if data is None:
        raise ToolError(f"Item #{item_id} not found")
    return {"item_id": item_id, "name": data["name"]}
