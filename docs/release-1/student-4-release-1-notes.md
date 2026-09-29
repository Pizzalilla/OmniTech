# Student 4 — Cart & Order Processing: Release 1 notes

Draft notes for the Release 1 report.

## What changed in Release 1

* **Grounded AI helper.** The helper now answers from real data, not just
  product names:
  * a new `product_specs` table (power draw, plug type, size, weight,
    capacity, clearances, energy rating, suggested accessory),
  * safety checks worked out in Python (power-point load, hardwired
    appliances, heavy deliveries, out-of-stock items),
  * store knowledge from the shared RAG server
    (`knowledge/appliance-installation-and-cart.md`, 7 sections).
* **Real Observe → Adapt.** Every number in the AI's answer is checked against
  the facts. One retry with feedback; if the answer is still unsupported, the
  facts-only answer is shown. The "✓ verified" footnote only appears when the
  check passes.
* **Shows its working.** Each answer lists its sources (cart database + RAG
  sections) and a "How the agent worked" trace of the Plan/Act/Observe/Adapt
  steps.
* **RAG status on the page.** A confidence badge (high / medium / low) when
  store knowledge is found, and the insufficient-context message ("I don't
  have enough information in the store knowledge…") when it isn't.
* **Switches for CI.** `RAG_ENABLED=false` skips the RAG call; `student-4.yml`
  sets `RAG_ENABLED=false` and `MCP_ENABLED=false`.
* **JSON mode.** `POST /api/orders/ai-validate-cart` with a JSON body returns
  the full result, so other services (or a future MCP/multi-agent server) can
  call it.

## MCP (Model Context Protocol)

* **Shared MCP server** built by Student 4 on branch `shared/mcp-server`
  (`ai-services/mcp-server`, port 6003, runs on the PC like Ollama/RAG). It
  speaks MCP over HTTP (JSON-RPC 2.0: `initialize`, `tools/list`,
  `tools/call`) and has a template so every student can add tools.
* **Tool boundaries:** every tool has an input schema that the server
  checks before the tool runs (missing, wrong-type and extra arguments are
  rejected), and tools are read-only - they can only `GET` from a
  student's own REST API, never open another student's database.
* **Student 4 tools:** `get_order_status(order_id)`, `get_cart()`,
  `get_product_specs(product_ids)`, backed by two new read-only endpoints
  (`GET /api/cart`, `GET /api/products/specs?ids=`).
* **MCP in my page:**
  * an **Order lookup (MCP tool)** card that calls `get_order_status` and shows
    the tool name, its inputs, the result (or "not found") and the raw MCP
    result;
  * the AI helper's Plan step now loads specs **via the MCP tool
    `get_product_specs`** (shown as "Cart database via MCP" in its sources),
    falling back to the database if MCP is off or offline.
* **Terminal validation:** `python validate.py` in `ai-services/mcp-server`
  (handshake, tool list, every tool called, boundary checks).

## Shared work done by Student 4

* The RAG server stays **outside Docker** (runs on the PC like Ollama, per the
  brief); every student container in `docker-compose.yml` now gets
  `RAG_HOST=http://host.docker.internal:6002`.
* New `POST /rag/retrieve` endpoint (retrieval without an LLM call) plus tests.
  It only adds to the server; `/rag/query` is unchanged.

## Architecture change since Release 0

Release 0 described a separate database service that the backend reached over
HTTP, started in the same container, and called splitting it into its own
container "a Release 1 clean-up". Instead, the service was simplified into
**one Flask app that uses SQLite directly** through `database/database.py`
(commit `6bca2bd`). Reason: the database only serves Student 4's own
feature, so an extra HTTP hop and container added failure points (the missing
`POST /orders` route in Release 0 came from that split) without any benefit.
Other services still reach the data through the REST API on port 5004.

## Ready for MCP

`agent.get_cart_facts()` and `db.get_product_specs()` are small functions with
plain inputs and outputs, so they can be exposed as MCP tools
(`get_cart`, `get_product_specs`) when the MCP server is built.
