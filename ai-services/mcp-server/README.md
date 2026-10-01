# Shared MCP Server (Release 1)

One shared **MCP (Model Context Protocol)** server that runs on the PC (not
in Docker), like Ollama and the RAG server. It gives every student's feature
a **toolbox**: each tool has a name, a description, an input schema and a
structured result, and any MCP client can list the tools and call them.

* Protocol: MCP over HTTP ("Streamable HTTP", JSON-response mode) - JSON-RPC 2.0
  messages POSTed to `/mcp`
* Port: **6003**
* Tools are **read-only**: they only `GET` from each student's own REST API,
  so every student still owns their own data (the tool boundary).

## Running it

```bash
cd ai-services/mcp-server
pip install -r requirements.txt
python server.py
```

Output: `MCP server starting on port 6003 with N tool(s): ...`

Env vars (all optional):

| Var | Default | Purpose |
|-----|---------|---------|
| `MCP_PORT` | `6003` | Port the server listens on |
| `STUDENT1_API` ... `STUDENT5_API` | `http://localhost:5001` ... `5005` | Where each student's REST API is |
| `MCP_SERVICE_TIMEOUT` | `10` | Seconds a tool waits for a student API |

Inside Docker, student containers reach the server with
`MCP_HOST=http://host.docker.internal:6003` (already in `docker-compose.yml`).

## Terminal validation (report evidence)

With the MCP server and the student services running:

```bash
python validate.py                  # every tool
python validate.py --only student4  # one student's tools
```

It checks the handshake, that every tool has a name / description / schema,
calls every tool with its example, and checks the boundaries (unknown tool,
missing argument, wrong type and extra arguments are all rejected).
`WARN` means a tool worked but its student service isn't running.

## Tools

| Tool | Owner | Inputs | Returns |
|------|-------|--------|---------|
| `get_order_status` | Student 4 | `order_id` (integer ≥ 1) | status, total, created date, line items |
| `get_cart` | Student 4 | – | current cart items, fulfilment, totals |
| `get_product_specs` | Student 4 | `product_ids` (1–20 integers) | power draw, plug, size, weight, clearances, energy rating |

## Adding your own tools

1. Copy `tools/_template.py` to `tools/studentN.py` (files starting with `_`
   are not loaded).
2. Set `SERVICE = "student-N"` and write one function per tool with the
   `@tool(...)` decorator: name, description, `properties` (input types),
   `required`, and an `example`.
3. Read data only with `service_get(SERVICE, "/api/...")` - a GET on your own
   REST API. It returns `None` for 404; raise `ToolError("...")` when the tool
   can't do its job.
4. Restart `server.py`, then run `python validate.py --only studentN`.

## Calling it from your feature's backend

Copy `client.py` into your service (e.g. as `backend/mcp_client.py`):

```python
import os
from mcp_client import McpClient, McpError

mcp = McpClient(os.getenv("MCP_HOST", "http://localhost:6003"))
res = mcp.call_tool("get_order_status", {"order_id": 5})
if res["isError"]:
    print(res["content"][0]["text"])        # e.g. "Order #999 not found"
else:
    print(res["structuredContent"])        # the tool's JSON result
```

`McpError` is raised when the server rejects the call (unknown tool, bad
arguments); `requests.RequestException` when the server isn't running. In CI
there is no MCP server, so check `MCP_ENABLED` (CI sets `MCP_ENABLED=false`).

## Raw protocol example

```bash
curl -s -X POST http://localhost:6003/mcp -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_order_status","arguments":{"order_id":5}}}'
```

Supported methods: `initialize`, `notifications/initialized`, `ping`,
`tools/list`, `tools/call`. `GET /health` lists the registered tools.

## Tests

```bash
python -m pytest tests/ -v
```

No student services are needed - the Student 4 API is faked, and the tests
also check that tools never use anything but GET.
