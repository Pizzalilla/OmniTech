"""
Tool registry for the shared MCP server.

Every student adds tools in tools/<student>.py with the @tool decorator.
Each tool has a name, a description, an input schema and a handler. The
registry checks the inputs before the handler runs, and the only way a tool
can reach a student's data is service_get() - a READ-ONLY (GET) call to that
student's own REST API. That is the tool boundary: tools can look, not change.
"""

import os

import requests

# SERVICES: where each student's REST API lives (override with env vars)
SERVICES = {
    "student-1": os.getenv("STUDENT1_API", "http://localhost:5001"),
    "student-2": os.getenv("STUDENT2_API", "http://localhost:5002"),
    "student-3": os.getenv("STUDENT3_API", "http://localhost:5003"),
    "student-4": os.getenv("STUDENT4_API", "http://localhost:5004"),
    "student-5": os.getenv("STUDENT5_API", "http://localhost:5005"),
}
SERVICE_TIMEOUT = int(os.getenv("MCP_SERVICE_TIMEOUT", "10"))

TOOLS = {}

JSON_TYPES = {"integer": int, "number": (int, float), "string": str, "boolean": bool, "array": list, "object": dict}


class ToolError(Exception):
    """A tool ran but could not do its job (shown to the caller as isError)."""


class InvalidArguments(Exception):
    """The caller sent arguments that don't match the tool's input schema."""


# DECORATOR: register a tool with its input schema
def tool(name, description, properties=None, required=(), example=None):
    def register(fn):
        if name in TOOLS:
            raise ValueError(f"Tool '{name}' is registered twice")
        TOOLS[name] = {
            "name": name,
            "description": description,
            "inputSchema": {
                "type": "object",
                "properties": properties or {},
                "required": list(required),
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
            "owner": fn.__module__.split(".")[-1],
            "example": example or {},
            "handler": fn,
        }
        return fn
    return register


# PUBLIC VIEW: what tools/list returns (no handler, no internal fields)
def list_tools():
    return [{k: t[k] for k in ("name", "description", "inputSchema", "annotations")} for t in TOOLS.values()]


# VALIDATION: check arguments against the input schema
def _check_type(value, schema, path):
    expected = schema.get("type")
    py_type = JSON_TYPES.get(expected)
    # bool is a subclass of int in Python, so reject it for integer/number
    if py_type and (not isinstance(value, py_type) or (expected in ("integer", "number") and isinstance(value, bool))):
        raise InvalidArguments(f"'{path}' must be {expected}")
    if expected == "array" and "items" in schema:
        for i, item in enumerate(value):
            _check_type(item, schema["items"], f"{path}[{i}]")
    if "minimum" in schema and value < schema["minimum"]:
        raise InvalidArguments(f"'{path}' must be at least {schema['minimum']}")
    if "maxItems" in schema and len(value) > schema["maxItems"]:
        raise InvalidArguments(f"'{path}' can have at most {schema['maxItems']} items")
    if "minItems" in schema and len(value) < schema["minItems"]:
        raise InvalidArguments(f"'{path}' needs at least {schema['minItems']} item(s)")


def validate_arguments(tool_def, arguments):
    if not isinstance(arguments, dict):
        raise InvalidArguments("arguments must be an object")
    schema = tool_def["inputSchema"]
    missing = [r for r in schema["required"] if r not in arguments]
    if missing:
        raise InvalidArguments(f"missing required argument(s): {', '.join(missing)}")
    extra = [k for k in arguments if k not in schema["properties"]]
    if extra:
        raise InvalidArguments(f"unknown argument(s): {', '.join(extra)}")
    for key, value in arguments.items():
        _check_type(value, schema["properties"][key], key)


# CALL: validate, then run the tool's handler
def call_tool(name, arguments):
    tool_def = TOOLS[name]
    validate_arguments(tool_def, arguments)
    return tool_def["handler"](**arguments)


# BOUNDARY: the only data access a tool gets - a GET to a known student API
def service_get(service, path, params=None):
    base = SERVICES.get(service)
    if base is None:
        raise ToolError(f"Unknown service '{service}'")
    if not path.startswith("/"):
        raise ToolError("path must start with /")
    try:
        resp = requests.get(f"{base}{path}", params=params, timeout=SERVICE_TIMEOUT)
    except requests.RequestException:
        raise ToolError(f"{service} API is not reachable at {base}")
    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        raise ToolError(f"{service} API returned HTTP {resp.status_code}")
    try:
        return resp.json()
    except ValueError:
        raise ToolError(f"{service} API did not return JSON")
