# Post-testing documentation — Cart & Order Processing (Student 4), Release 1

## 1. Summary

| Metric | Result |
|--------|--------|
| Agent + route tests (`tests/test_agent.py`) | **20 / 20 passing** (fake LLM + fake RAG, no Ollama; also passes with `RAG_ENABLED=false` as in CI) |
| Live API tests (`tests/test_orders_api.py`) | **17 / 17 passing** against a running app + real RAG server + stand-in Ollama |
| Shared RAG server tests (`ai-services/rag-server/tests`) | **13 / 13 passing** (11 existing + 2 new for `/rag/retrieve`) |
| Live run with real `llama3.2` | _To fill in after running with Ollama (see section 4)_ |
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

## 4. Live run with real Ollama (to do on a machine with Ollama)

```bash
# terminal 1 - shared RAG server
cd ai-services/rag-server && python server.py
# terminal 2 - Student 4 app
python student-4/backend/main.py
# terminal 3 - all live tests, including the two AI ones
pytest student-4/tests/test_orders_api.py -v
```

Or with Docker: start the RAG server on the PC first, then `docker-compose up --build` (containers use `RAG_HOST=http://host.docker.internal:6002`).

| Check | Result |
|-------|--------|
| `test_ai_helper_custom_question` | _pass / fail_ |
| `test_ai_helper_grounded_json` | _pass / fail_ |
| Auto Audit Cart — status shown (verified / fallback) | _…_ |
| Typed question — status and number of attempts | _…_ |

## 5. Defects found and fixed during testing

| Defect | Fix |
|--------|-----|
| AI prompt only had product names, so the model invented wattages and sizes | Specs table + facts in the prompt |
| Footnote always said "✓ Verified" even though nothing was checked | Footnote now depends on the verifier result |
| AI text was inserted into the page unescaped | Escaped with `markupsafe.escape` |
| Demo cart product ids 501–504 clashed with different products in the seeded orders | Demo cart moved to ids 511–514 |
| Adding product names to every RAG query made all questions retrieve the same section | Names only added for the Auto Audit query |
| OpenAI client retried a dead Ollama several times before failing | Replaced with one direct `requests` call to Ollama's `/api/chat` |

## 6. Known limitations

* The verifier checks numbers only — a wrong statement with no number in it is
  not caught.
* Microwave "1000W" is its cooking output; the spec table stores its 1500 W
  power draw, which is what the power-point check uses.
* Product specs are stored in Student 4's own database; in a later release they
  could come from Student 1's catalog service or an MCP tool.
