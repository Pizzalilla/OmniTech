# Shared Agentic Loop MCP & RAG Validation

The team's shared, **non-containerised** **Plan -> Act -> Observe -> Adapt**
loop (spec section 4.3), extended for Release 1 with **MCP** and **RAG**
validation modes alongside the Release 0 **AI-mode**.

| Stage | What it does |
|-------|--------------|
| PLAN | Gathers evidence for the mode: an MCP tool result, a RAG grounded answer, or none (AI-mode) |
| ACT | Local Ollama answers the request - only from the evidence in MCP/RAG modes |
| OBSERVE | Local Ollama checks the answer is grounded in the evidence (MCP/RAG) or on-topic (AI-mode) |
| ADAPT | If OBSERVE rejects, its feedback becomes a correction and ACT retries (`MAX_RETRIES`, default 1) |

If PLAN gets no evidence (MCP error, RAG insufficient context, server down)
the loop fails before ACT runs, so it never invents an answer.

## Running it

Needs local Ollama running with `llama3.2` pulled (`OLLAMA_HOST`, default
`http://localhost:11434`). Start the student services if you want to validate
their MCP tools:

```bash
docker compose up --build
```

### Start MCP & RAG server
In a new terminal:
```bash
cd ai-services/mcp-server
python3 server.py
```

In another terminal:
```bash
cd ai-services/rag-server
python3 server.py
```

### Terminal Validation
With both MCP and RAG servers running, in a new terminal:

**AI-mode (Release 0) - local LLM only, no MCP/RAG (expected PASS):**
```bash
cd ai-services/multi-agent-server
python3 validate.py --mode ai --question "What does a warranty usually cover?" --output ai_pass.json
```

**RAG mode - grounded answer (expected PASS, usually in 1 attempt):**
```bash
python3 validate.py --mode rag --question "What is your return policy?" --output rag_pass.json
```

**RAG mode - insufficient context (expected FAIL at PLAN, ACT never runs):**
```bash
python3 validate.py --mode rag --question "What is the capital of France?" --output rag_insufficient.json
```

**MCP mode - rejected request (expected FAIL at PLAN):**
```bash
python3 validate.py --mode mcp --tool get_order_status --args '{"order_id": 0}' --output mcp_rejected.json
```
The MCP server rejects `order_id: 0` against the tool's input schema
(minimum 1), proving the tool boundary and that the loop fails without evidence.

**MCP mode - successful tool call (expected PASS):** use any tool whose
student service is running, e.g. with the student-3 service up (once the
student-3 `get_saved_recommendations` tool is merged into `main`):
```bash
python3 validate.py --mode mcp --tool get_saved_recommendations --args '{"session_id": 1}' --output mcp_pass.json
```

`--output` saves the final result as JSON for the report; omit it to only print.

> Note: Student 4's tools (`get_order_status`, `get_cart`, `get_product_specs`)
> call `/api/orders/<id>`, `/api/cart` and `/api/products/specs`. Those routes
> exist on the `syk-student4` branch but not yet on `main`, so until it is
> merged they return "not found" or "not reachable" for any input.

## Tests
```bash
cd ai-services/multi-agent-server
python3 -m pytest tests/ -v
```
Unit tests fake MCP, RAG and Ollama. The two live tests skip automatically
when the MCP server, RAG server or Ollama isn't running.
