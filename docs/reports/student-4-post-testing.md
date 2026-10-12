# Post-testing documentation — Cart & Order Processing (Student 4), Release 1

## 1. Summary

| Metric | Result |
|--------|--------|
| Agent + route tests (`tests/test_agent.py`) | **23 / 23 passing** (fake LLM + fake RAG, no Ollama; also passes with `RAG_ENABLED=false` as in CI) |
| Live API tests (`tests/test_orders_api.py`) | **20 / 20 passing** against a running app + real RAG server + stand-in Ollama |
| MCP tests (`tests/test_mcp.py`) | **12 / 12 passing** (fake MCP client) |
| Shared MCP server tests (`ai-services/mcp-server/tests`) | **23 / 23 passing** (student APIs faked) |
| MCP terminal validation (`validate.py`, all servers running) | **16 passed, 0 warnings, 0 failed** |
| Shared RAG server tests (`ai-services/rag-server/tests`) | **13 / 13 passing** (11 existing + 2 new for `/rag/retrieve`) |
| Live run with real `llama3.2` (section 4) | **40 / 40 checks passed** |
| CI | `student-4.yml` runs the API suite, agent tests, RAG tests and the Docker build, with `RAG_ENABLED=false` / `MCP_ENABLED=false` |

## 2. Automated results

| Area | Cases | Status |
|------|-------|--------|
| Plan: specs from `product_specs`, safety checks, DB upgrade | P1–P5 | pass |
| Observe: number verifier and unit parsing | O1–O3 | pass |
| Act/Adapt: verified, retry-with-feedback, fallback, offline | L1–L4 | pass |
| RAG client: retrieve, old-server fallback, offline | R1–R3 | pass |
| RAG server `/rag/retrieve` | R4 | pass |
| Route: HTML, escaping, offline banner, JSON | H1–H4 | pass |
| RAG states: confidence badge, insufficient-context message, `RAG_ENABLED=false` | H5–H7 | pass |
| Release 0 regression (CRUD, cart, checkout, history) | 15 cases | pass |

The existing RAG retriever tests (warranty and shipping questions still return
their own documents first) passed after the Student 4 knowledge file was added,
so the new file does not crowd out other features' knowledge.

## 3. Integration run (HTTP, all services running)

Run with the real RAG server (`server.py`, 32 knowledge chunks loaded), the
real Student 4 app, and a small stand-in for Ollama's `/api/chat` that gives a
made-up weight on the first try:

| Check | Result |
|-------|--------|
| `GET :6002/health` | `{"chunks_loaded": 32, "status": "ok"}` |
| Question "What is the estimated weight in kg for this 500L fridge for delivery?" | RAG returned *Fridge Ventilation Clearance* + *Delivery of Large and Heavy Appliances*; first answer "95kg" rejected by Observe; retry answered "82 kg"; `status=verified`, 2 attempts |
| Auto Audit Cart | 3 checks shown (82 kg delivery, out-of-stock microwave, 5200 W on one power point), 3 knowledge sections cited, all 5 numbers verified |
| Off-topic question "Who won the football last night?" | RAG `insufficient`; page shows "I don't have enough information in the store knowledge…" |
| "Can I share a power point for the cooktop and air fryer?" | RAG `ok`, badge "RAG confidence: high", 3 sections cited |
| Ollama stopped | `ai-alert-box error`, "AI Helper Offline", and the fridge's real specs still shown |

### MCP integration run

| Check | Result |
|-------|--------|
| Order lookup #5 | `get_order_status({"order_id": 5})` → success box: Processing, $1,299.50, 1 item |
| Order lookup #999 | warning box "Order #999 not found" (tool error, not a crash) |
| AI helper question | trace: "loaded specs for 4/4 cart items via MCP tool get_product_specs"; MCP server log shows the call |

## 4. Live run on the PC with real Ollama (llama3.2)

Run on 29 Sep 2026 (Windows, Python 3.14, Ollama llama3.2) with the RAG
server, MCP server and Student 4 app all running. Full output:
`docs/reports/student-4-release-1-live-run.txt` - **40 / 40 checks passed**.

| Area | Result |
|------|--------|
| pytest: agent + MCP / live API (real llama3.2) / RAG server / MCP server | 35 / 20 / 13 / 23 passed |
| MCP `validate.py` | 16 passed, 0 warnings, 0 failed |
| RAG `query.py "What is your return policy?"` | grounded answer with citations, confidence medium |
| Auto Audit Cart | green box, warnings (5200W / 82 kg / out of stock), "Cart database via MCP", RAG badge, ~12 s |
| Dimensions | "700mm W x 1780mm H x 720mm D … rear 50mm, side 20mm, top 50mm" - 7 numbers verified |
| Weight | "weighs 82 kg … two-person team … measure doorways" - verified |
| AU Power | "No … combined power draw exceeds the 2400W limit … separate power points" - verified |
| Energy Stars | "4-star energy rating … 390 kWh/year" - verified |
| "Who won the football last night?" | RAG insufficient context; AI: "I don't have that information" |
| MCP order lookup #5 / #999 | success (Processing) / "Order #999 not found" |
| MCP server off | lookup says offline; AI helper falls back to the database |
| RAG server off | AI helper still answers, "RAG server offline" shown |
| Ollama unreachable | red "AI Helper Offline" box, real specs still shown |
| Release 0 | quantity, pickup/delivery fee, checkout → MCP finds the new order, status update, delete |

Typical answer time with llama3.2 on this PC: 3–5 s per question, ~12 s for the audit.

## 5. Defects found and fixed during testing

| Defect | Fix |
|--------|-----|
| AI prompt only had product names, so the model invented wattages and sizes | Specs table + facts in the prompt |
| Footnote always said "✓ Verified" even though nothing was checked | Footnote now depends on the verifier result |
| AI text was inserted into the page unescaped | Escaped with `markupsafe.escape` |
| Demo cart product ids 501–504 clashed with different products in the seeded orders | Demo cart moved to ids 511–514 |
| Adding product names to every RAG query made all questions retrieve the same section | Names only added for the Auto Audit query |
| Live llama3.2 audit said the plug-in cooktop needs "a 32A hardwired circuit", and called 4 stars "the highest rating in Australia" - claims with no new number, so the number check let them through | Facts now say "plugs into a normal power point - no hardwiring or electrician needed"; prompt says to apply store rules only to matching products; new **claim check** in Observe rejects hardwiring/electrician and "highest rating" claims when the facts don't support them (retry once). Re-run: both gone |
| `OLLAMA_HOST=0.0.0.0:11434` (Windows Ollama setting) made every AI call fail with InvalidSchema | `ollama_url()` adds `http://` and swaps 0.0.0.0 for 127.0.0.1 |
| OpenAI client retried a dead Ollama several times before failing | Replaced with one direct `requests` call to Ollama's `/api/chat` |

## 6. Known limitations

* The verifier checks numbers plus a few known claim types (hardwiring,
  "highest rating"); other wrong statements with no number in them can still
  get through.
* Microwave "1000W" is its cooking output; the spec table stores its 1500 W
  power draw, which is what the power-point check uses.
* Product specs are stored in Student 4's own database; in a later release they
  could come from Student 1's catalog service or an MCP tool.
