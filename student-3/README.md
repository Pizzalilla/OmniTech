# AI Product Consultant (Student 3)

Conversational, catalog-grounded product advice for the OmniTech Marketplace.
The service runs an agentic loop over a local Ollama model and owns three
database tables that no other microservice touches directly.

## Stack

| Layer     | Choice                                               |
|-----------|-----------------------------------------------------|
| Backend   | Python 3.11, Flask (REST API + HTMX fragments)      |
| Frontend  | HTML + HTMX 2, shared OmniTech CSS design system    |
| Database  | SQLite (`consultant.db`), raw SQL, no ORM           |
| AI        | Local Ollama HTTP API (`llama3.2` by default)       |

## Layout

```
student-3/
  backend/
    main.py       Flask app: pages, REST API, HTMX partials
    agent.py      Plan -> Act -> Observe -> Adapt consultation loop
    catalog.py    Mock product catalog + keyword search / validation helpers
  database/
    database.py   Schema, connection helper, demo seed data
  frontend/
    index.html           Static landing page for the shared gateway
    templates/           Jinja templates (chat UI, dashboard, HTMX partials)
    static/style.css     The single stylesheet (served at /static/style.css);
                         palette tokens are the shared OmniTech design-system values
  tests/          pytest suite (routes, agent loop, catalog)
  Dockerfile
```

## Running

### With the shared stack

```
docker compose up student-3 ollama-service
```

Chat UI: <http://localhost:5003/> — Dashboard: <http://localhost:5003/dashboard>

### Standalone

```
cd student-3
pip install -r requirements.txt
python backend/main.py            # http://localhost:5000
```

The database is created and seeded automatically on first start. If Ollama is
not reachable the consultant degrades to a deterministic catalog keyword match
so the UI still works.

### Environment

| Variable        | Default                  | Purpose                         |
|-----------------|--------------------------|---------------------------------|
| `OLLAMA_HOST`   | `http://localhost:11434` | Ollama base URL                 |
| `OLLAMA_MODEL`  | `llama3.2`               | Model name (team default)       |
| `OLLAMA_TIMEOUT`| `120`                    | Per-request timeout (seconds)   |
| `DB_PATH`       | `database/consultant.db` | SQLite file location            |
| `PORT`          | `5000`                   | HTTP port                       |

## Data ownership

This service is the only writer and reader of:

* `ConsultationSessions` — `id`, `user_id`, `title`, `created_at`, `updated_at`
* `ChatLogs` — `id`, `session_id`, `sender` (`user`/`ai`), `message_text`, `created_at`
* `SavedRecommendations` — `id`, `session_id`, `product_ids`, `summary`, `tags`, `created_at`

Other microservices must go through the REST API below.

## REST API

### Consultation sessions

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET    | `/api/sessions` | — | optional `?user_id=` filter |
| POST   | `/api/sessions` | `{title?, user_id?}` | |
| GET    | `/api/sessions/<id>` | — | returns session + messages + recommendations |
| PUT    | `/api/sessions/<id>` | `{title}` | |
| DELETE | `/api/sessions/<id>` | — | cascades to logs and recommendations |

### Chat logs

| Method | Path | Body |
|--------|------|------|
| GET    | `/api/sessions/<id>/messages` | — |
| POST   | `/api/sessions/<id>/messages` | `{sender, message_text}` |
| DELETE | `/api/sessions/<id>/messages` | — (clear history, keep session) |
| DELETE | `/api/messages/<id>` | — |

### Saved recommendations

| Method | Path | Body |
|--------|------|------|
| GET    | `/api/sessions/<id>/recommendations` | — |
| POST   | `/api/recommendations` | `{session_id, product_ids[], summary?, tags?}` |
| PUT    | `/api/recommendations/<id>` | `{tags?, summary?}` |
| POST   | `/api/recommendations/<id>/tags` | `{tag}` or form `tag` (add one) |
| DELETE | `/api/recommendations/<id>` | — |

### Consultation

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST   | `/api/chat` | `{session_id, message}` | JSON, or an HTMX HTML fragment when sent with `HX-Request: true` |

## Agentic loop

`agent.run_consultation()` implements four stages:

1. **Plan** — `catalog.search()` selects catalog rows relevant to the request and
   builds a plain-text context block.
2. **Act** — a structured prompt (system rules + catalog + recent history) is sent
   to Ollama with `format: json`.
3. **Observe** — `agent.observe()` checks the reply parses as JSON with the
   required fields and that every `recommended_product_ids` entry exists in the
   catalog; it also flags product ids named in the prose but missing from the
   list.
4. **Adapt** — on failure a single corrective re-prompt is sent that quotes the
   exact problems. If it still fails, or Ollama is unreachable, the deterministic
   catalog fallback answer is used. The final reply and any recommendation are
   then persisted.

## Tests

```
cd student-3
python -m pytest tests/ -v
```

See `docs/reports/student-3-pre-testing.md` and
`docs/reports/student-3-post-testing.md` for the test plan and results.
