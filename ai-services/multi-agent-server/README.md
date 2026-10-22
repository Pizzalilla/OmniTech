# Multi-Agent Server (Release 2)

One shared, **non-containerised** server (port **6004**) that runs
**Planner -> Worker -> Reviewer -> Human Review** for any student's feature.
It runs on the PC like Ollama, the RAG server and the MCP server - it is not
in Docker Compose.

| Agent | Job |
|-------|-----|
| Planner | Reads the task and the evidence names, writes a plan (goal, steps, evidence needed, success criteria). Doesn't answer the task. |
| Worker | Follows the plan using **only** the evidence it was given. Lists the evidence it used and anything it couldn't do. |
| Reviewer | Checks the Worker's output against the plan and the evidence. Gives `pass`, `needs_changes` or `fail`, plus risks and recommendations. Also runs code checks (e.g. Worker citing evidence that was never sent). |
| Human | Final say: `approve`, `correct` (with a corrected answer), `partial` (with a note) or `reject` (with a note). |

**Your backend sends the evidence.** The server never fetches data itself, so
it doesn't need to know anything about carts, tickets or warranties. Gather
your facts (from your DB, MCP or RAG) and send them in `evidence`.

Every step is written to:

- `logs/audit.jsonl` - append-only audit log, one line per event
- `logs/history/<workflow id>.json` - the full workflow (plan, work, review, decision)

`logs/` is git-ignored. Copy the files you need into your evidence folder for the report.

## Running it

Needs Ollama running with `llama3.2` (`OLLAMA_HOST`, default `http://localhost:11434`).

```bash
cd ai-services/multi-agent-server
pip install -r requirements.txt
python server.py            # http://localhost:6004
```

| Env var | Default |
|---------|---------|
| `MULTI_AGENT_PORT` | `6004` |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | `http://localhost:11434` / `llama3.2` |
| `OLLAMA_TIMEOUT` | `120` (seconds, per agent) |
| `MULTI_AGENT_LOG_DIR` | `./logs` |

## Calling it from your backend

From a Docker container use `http://host.docker.internal:6004` (add it as
`MULTI_AGENT_HOST` in `docker-compose.yml`, like `MCP_HOST` and `RAG_HOST`).

```python
resp = requests.post(f"{MULTI_AGENT_HOST}/workflow/start", timeout=400, json={
    "student": "student-2",
    "task": "Check this customer's details before saving",
    "evidence": {"customer": {...}, "rules": [...]},
})
# 201 -> status "awaiting_human"   503 -> Ollama down (status "failed")   400 -> bad input
workflow = resp.json()        # workflow["plan"], ["work"], ["review"], ["id"]

requests.post(f"{MULTI_AGENT_HOST}/workflow/{workflow['id']}/decision", json={
    "decision": "partial", "reviewer": "staff", "note": "Address ok, phone needs checking",
})
# 200 ok   400 missing note / corrected_answer   404 unknown id   409 already decided
```

| Endpoint | What it does |
|----------|--------------|
| `GET /health` | status, model, whether Ollama is reachable |
| `POST /workflow/start` | `{student, task, evidence}` - runs the three agents |
| `POST /workflow/<id>/decision` | `{decision, reviewer, note, corrected_answer}` |
| `GET /workflow/<id>` | one workflow plus its audit events |
| `GET /workflows?student=student-4` | workflow history, newest first |
| `GET /audit?workflow_id=<id>` | raw audit log events |

## Terminal

```bash
# runs right here in the terminal, then asks you for the human decision
python cli.py run --student student-4 --task "Check this cart is ready for checkout" --evidence examples/student4_cart.json

# same thing but through the running server
python cli.py run --student student-4 --task "Check this cart" --evidence examples/student4_cart.json --server http://localhost:6004

python cli.py list --student student-4      # workflow history
python cli.py show wf-1a2b3c4d              # one workflow + its audit log
python cli.py decide wf-1a2b3c4d --decision approve
```

## Tests

```bash
python -m pytest tests/test_multi_agent.py -v
```

Ollama is faked, so these run in CI with nothing else running.

---

# Shared Agentic Loop - MCP & RAG Validation

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
