"""
Student 3 - AI Product Consultant tools.

All tools are read-only: they call Student 3's REST API (port 5003) with GET.
"""

from registry import ToolError, service_get, tool

SERVICE = "student-3"


# TOOL: a consultation session's saved product recommendations
@tool(
    name="get_saved_recommendations",
    description="Get the AI Product Consultant's saved product recommendations for one consultation session.",
    properties={"session_id": {"type": "integer", "minimum": 1,
                                "description": "Consultation session id, e.g. 1"}},
    required=["session_id"],
    example={"session_id": 1},
)
def get_saved_recommendations(session_id):
    data = service_get(SERVICE, f"/api/sessions/{session_id}/recommendations")
    if data is None:
        raise ToolError(f"Session #{session_id} not found")
    return {"session_id": session_id, "recommendations": data}
