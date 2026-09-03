# Pre-testing documentation — AI Product Consultant (Student 3)

## 1. Scope

The microservice under test provides:

* an HTMX chat interface for product consultations,
* a dashboard of past sessions and saved recommendations,
* a REST API owning `ConsultationSessions`, `ChatLogs` and `SavedRecommendations`,
* an agentic loop (Plan → Act → Observe → Adapt) over a local Ollama model.

## 2. Test approach

| Level | Tool | What it covers |
|-------|------|----------------|
| Unit | `pytest` | `agent.observe` validation rules, `agent.run_consultation` fallback/adapt behaviour, `catalog` helpers |
| Integration | `pytest` + Flask test client | every REST route, HTMX partial routes, content negotiation on `/api/chat` |
| Manual | Browser | HTMX swaps (send message, add tag, clear history), dashboard rendering, offline degradation |
| CI | GitHub Actions (`.github/workflows/student-3.yml`) | `py_compile` of all backend modules, full pytest run, Docker image build, on every push/PR touching `student-3/**` |

### Environmental assumptions

* Ollama is **not** available in CI or local unit runs. The loop must therefore
  degrade to the deterministic catalog fallback and still persist a reply. Tests
  that need a "good" model answer monkeypatch `agent.act`.
* Each test gets an isolated SQLite file (`tmp_path`) and re-seeds, so
  destructive cases cannot affect others.

## 3. Entry criteria

* `pip install -r student-3/requirements.txt` succeeds.
* `python -m py_compile` passes for `backend/main.py`, `backend/agent.py`,
  `backend/catalog.py`, `database/database.py`.
* Database seeds with ≥10 rows in each of the three tables.

## 4. Planned test cases

### 4.1 Agent loop (`tests/test_agent.py`)

| ID | Case | Expected |
|----|------|----------|
| A1 | `observe` on a well-formed, catalog-consistent answer | `ok=True`, no issues |
| A2 | `observe` on non-JSON text | `ok=False`, `data=None` |
| A3 | `observe` on an answer citing a non-catalog id | `ok=False`, hallucination issue, bad id scrubbed |
| A4 | `observe` when the prose names an id absent from `recommended_product_ids` | `ok=False`, consistency issue |
| A5 | `run_consultation` with Ollama unreachable | fallback answer, `meta.used_fallback=True`, ids all valid |
| A6 | `run_consultation` where the first model answer is invalid, second is valid | exactly one re-prompt, `meta.reprompts=1`, `used_fallback=False` |

### 4.2 Catalog (`tests/test_catalog.py`)

| ID | Case | Expected |
|----|------|----------|
| C1 | every product has all required keys, integer price | passes |
| C2 | product ids unique | passes |
| C3 | `get_many` drops unknown ids and de-duplicates | order preserved |
| C4 | `search` on a headphones query | first hit is a `Headphones` product |
| C5 | `search` on nonsense | never returns an empty list |
| C6 | `context_block` | contains ids and `$` prices |

### 4.3 Sessions API (`tests/test_app.py`)

| ID | Case | Expected |
|----|------|----------|
| S1 | `GET /api/sessions` | ≥10 rows |
| S2 | `GET /api/sessions?user_id=` | only that user's rows |
| S3 | `POST /api/sessions` with `user_id` | 201, echoes title + user_id |
| S4 | `GET /api/sessions/<id>` | bundle of session + messages + recommendations |
| S5 | `GET /api/sessions/9999` | 404 |
| S6 | `PUT /api/sessions/<id>` | 200, new title |
| S7 | `PUT` with no title | 400 |
| S8 | `DELETE /api/sessions/<id>` then `GET` | 200 then 404 |
| S9 | `DELETE` cascades | child `messages` route 404s afterwards |

### 4.4 Chat logs API

| ID | Case | Expected |
|----|------|----------|
| L1 | `GET /api/sessions/1/messages` | ≥2 rows |
| L2 | `POST` a message | 201 |
| L3 | `POST` with `sender="robot"` | 400 |
| L4 | `DELETE /api/sessions/1/messages` (clear history) | 200, list now empty |
| L5 | `DELETE /api/messages/<id>` | 200 |

### 4.5 Saved recommendations API

| ID | Case | Expected |
|----|------|----------|
| R1 | `GET /api/sessions/1/recommendations` | rows include resolved `products` |
| R2 | `POST /api/recommendations` with valid ids | 201, ids stored |
| R3 | `POST` with only unknown ids | 400 |
| R4 | `PUT /api/recommendations/1` tags | 200, tags updated |
| R5 | `POST /api/recommendations/1/tags` `tag="Great Value"` | 200, stored as `great-value` |
| R6 | `POST .../9999/tags` | 404 |
| R7 | `DELETE /api/recommendations/1` | 200 |

### 4.6 Consultation endpoint

| ID | Case | Expected |
|----|------|----------|
| X1 | `POST /api/chat` `{}` | 400 |
| X2 | `POST /api/chat` unknown session | 404 |
| X3 | `POST /api/chat` (Ollama offline) | 200, non-empty reply, `meta.used_fallback=True`, user+ai rows persisted |
| X4 | `POST /api/chat` (model patched to valid answer) | 200, recommendation auto-saved |
| X5 | `POST /api/chat` with `HX-Request: true` | HTML fragment containing `msg--ai` and an out-of-band swap |

### 4.7 Pages and partials

| ID | Case | Expected |
|----|------|----------|
| P1 | `GET /` | 200, contains "AI Product Consultant" |
| P2 | `GET /dashboard` | 200, both section headings present |
| P3 | `GET /partials/session-list` | 200, `session-item` markup |
| P4 | `GET /partials/chat/1` | 200, `chat-messages` and a "Clear history" control |
| P5 | `GET /partials/recommendations/1` | 200, `reco` markup |
| P6 | `GET /static/style.css` | 200, the single stylesheet |

## 5. Exit criteria

* All 44 automated tests pass locally and in CI.
* Docker image builds.
* Manual browser pass: message send, tag add, clear history and dashboard all
  update without a full page reload; no console errors.
