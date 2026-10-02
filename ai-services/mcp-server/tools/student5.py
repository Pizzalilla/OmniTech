"""
Student 5 - AI Warranty Evaluating tools.

All tools are read-only: they call Student 5's REST API (port 5005) with GET.
"""

from registry import ToolError, service_get, tool

SERVICE = "student-5"


# TOOL: a consultation session's saved product recommendations