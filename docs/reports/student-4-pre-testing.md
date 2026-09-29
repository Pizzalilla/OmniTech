# Pre-testing documentation — Cart & Order Processing (Student 4), Release 1

## 1. Scope

The microservice under test (port 5004) provides:

* an HTMX cart page (quantities, fulfilment toggle, checkout, past orders),
* a REST API with full CRUD on `orders` / `order_line_items`, plus saved carts,
* **Release 1:** a grounded AI helper (`backend/agent.py`) that answers cart
  questions and audits the cart using a Plan → Act → Observe → Adapt loop:
  * **Plan** – loads real specs for every cart item from the new
    `product_specs` table, runs Python safety checks (power-point load,
    hardwired appliances, heavy items, stock) and retrieves store knowledge from
    the shared RAG server (`POST /rag/retrieve`),
  * **Act** – asks the shared Ollama model (`llama3.2`) to answer using only
    those facts,
  * **Observe** – extracts every number + unit from the answer and checks it
    against the facts,
  * **Adapt** – retries once with feedback; if the answer still has unsupported
    numbers (or Ollama is offline) it shows a facts-only answer instead.

Out of scope for Release 1: the MCP server (the agent's data functions
`get_cart_facts` / `db.get_product_specs` are written so they can become MCP
tools later).

## 2. Test approach

| Level | Tool | What it covers |
|-------|------|----------------|
| Unit | `pytest` (`tests/test_agent.py`) | fact loading, safety checks, number verifier, retry/fallback/offline paths, RAG client incl. old-server fallback |
| Integration | `pytest` + Flask test client (`tests/test_agent.py`) | `/api/orders/ai-validate-cart` HTML and JSON responses, HTML escaping of AI text |
| Live API | `pytest` + `requests` (`tests/test_orders_api.py`) | CRUD, cart/HTMX routes, checkout, and the AI helper against a running app + RAG server + Ollama |
| Shared RAG | `pytest` (`ai-services/rag-server/tests`) | new `/rag/retrieve` endpoint and the new Student 4 knowledge file loading |
| Manual | Browser | Auto Audit and question flows, sources list, "How the agent worked" trace, offline banner |
| CI | GitHub Actions (`student-4.yml`) | live API suite (AI cases deselected), agent tests, RAG server tests, Docker build |

### Environmental assumptions

* Ollama is **not** available in CI, so `test_agent.py` replaces the LLM with a
  fake (`monkeypatch agent.ask_llm`) and the RAG call with a fake
  (`agent.retrieve_knowledge`).
* Each agent test uses its own temporary `orders.db`, so tests never change the
  demo data.
* Live AI tests need Ollama (`llama3.2`) and the RAG server running.

## 3. Entry criteria

* `pip install -r student-4/requirements.txt` succeeds.
* `python student-4/database/init_db.py` seeds 10 orders, 2 saved carts and
  8 product spec rows.
* An existing `orders.db` without the `product_specs` table is upgraded
  automatically on first use.

## 4. Planned test cases

### 4.1 Agent — Plan (facts + checks)

| ID | Case | Expected |
|----|------|----------|
| P1 | Demo cart facts joined with `product_specs` | 4/4 items have specs; fridge 700 mm wide, 82 kg |
| P2 | Safety checks on the demo cart | 5200 W combined heating load flagged vs 2400 W power point; 82 kg two-person delivery; microwave out of stock |
| P3 | Hardwired 7200 W induction cooktop (#505) | "licensed electrician" warning |
| P4 | Product with no specs | `has_specs=False`, "no specs on file" warning |
| P5 | Old `orders.db` with no `product_specs` table | table created and seeded on first read |

### 4.2 Agent — Observe (number verifier)

| ID | Case | Expected |
|----|------|----------|
| O1 | Answer using spec numbers in other units (70 cm, 1.78 m, 3500 W sum, 14.6 A) | no unsupported numbers |
| O2 | Answer with made-up numbers (95 cm, 60 kg, 5-star) | all three reported |
| O3 | Number parsing: `2,000W`, `2kW`, `5 cm`, `10 amps`, `20 litres`, `3 minutes` | first five parsed, "minutes" ignored |

### 4.3 Agent — Act / Adapt (full loop)

| ID | Case | Expected |
|----|------|----------|
| L1 | Grounded answer first time | `status=verified`, 1 attempt; prompt contains real specs and RAG knowledge |
| L2 | First answer invents a number, second is grounded | `status=verified`, 2 attempts; 2nd prompt names the bad number |
| L3 | Model keeps inventing numbers | `status=fallback`; facts-only answer shown, invented number not shown |
| L4 | Ollama unreachable | `status=offline`; facts-only answer shown |

### 4.4 RAG client

| ID | Case | Expected |
|----|------|----------|
| R1 | RAG server has `/rag/retrieve` | chunks returned, `/rag/retrieve` called |
| R2 | Older RAG server (404 on `/rag/retrieve`) | falls back to `/rag/query` citations |
| R3 | RAG server down | `([], "offline")`, helper still works |
| R4 | `/rag/retrieve` on the server | returns Student 4 knowledge, never calls Ollama; 400 on empty query; `insufficient_context` on nonsense |

### 4.5 Route

| ID | Case | Expected |
|----|------|----------|
| H1 | HTMX form post | `ai-alert-box success`, sources list, "How the agent worked" trace |
| H2 | AI text containing `<script>` | escaped in the HTML |
| H3 | Ollama down | `ai-alert-box error` + "AI Helper Offline" + real facts |
| H4 | JSON post (other services) | JSON result with `status`, `knowledge`, `trace` |
| H5 | RAG found knowledge | "RAG confidence: high/medium/low" badge |
| H6 | RAG found nothing (off-topic question) | insufficient-context message shown, answer uses product data only |
| H7 | `RAG_ENABLED=false` (CI) | RAG not called, "RAG disabled" shown |

### 4.6 Existing Release 0 cases (regression)

Health, orders read/CRUD lifecycle/validation, saved cart, index page, cart
view + stock dots, quantity change, fulfilment toggle, order history, checkout
saves an order — all in `tests/test_orders_api.py`, must still pass.

## 5. Exit criteria

* All `test_agent.py`, `test_orders_api.py` and RAG server tests pass.
* CI green on `syk-student4`.
* Manual pass shows sources, checks and the agent trace for both the audit and
  a typed question, and the offline banner when Ollama is stopped.
