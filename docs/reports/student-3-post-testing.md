# Post-testing documentation — AI Product Consultant (Student 3)

## 1. Summary

| Metric | Result |
|--------|--------|
| Automated tests | **44 / 44 passing** |
| Test files | `tests/test_app.py` (32), `tests/test_agent.py` (6), `tests/test_catalog.py` (6) |
| Runtime | ~0.2 s locally |
| `py_compile` | passes for `main.py`, `agent.py`, `catalog.py`, `database.py` |
| CI | GitHub Actions `student-3.yml` — syntax check, pytest, Docker build |
| Manual browser pass | completed, no console errors |

## 2. Automated results

All planned cases from the pre-testing plan executed and passed:

```
tests/test_agent.py ......                                          [ 13%]
tests/test_app.py ................................                  [ 86%]
tests/test_catalog.py ......                                        [100%]
44 passed
```

Coverage by area:

| Area | Cases | Status |
|------|-------|--------|
| Agent Observe validation (JSON shape, hallucinated ids, prose/list consistency) | A1–A4 | pass |
| Agent Adapt + fallback (offline, one corrective re-prompt) | A5–A6 | pass |
| Catalog integrity and search | C1–C6 | pass |
| Sessions CRUD incl. `user_id` filter and delete cascade | S1–S9 | pass |
| Chat logs CRUD incl. clear-history and single-message delete | L1–L5 | pass |
| Saved recommendations CRUD incl. add-tag slugging and catalog guard | R1–R7 | pass |
| `/api/chat` validation, persistence, auto-save, HTMX negotiation | X1–X5 | pass |
| Pages and HTMX partials, static stylesheet | P1–P6 | pass |

## 3. Manual verification

Performed against a running instance with **Ollama offline** (worst case):

Layout: rounded white panel on a tinted frame, a slim left icon rail, a centred
hero (headline + mascot) with a rounded composer card and quick-prompt chips.
Past consultations live in a collapsible left sidebar (toggled from the rail, or
the chevron in the sidebar header); on wide screens it starts open. One Dashboard
link, top-right. A single stylesheet, `frontend/static/style.css`, served at
`/static/style.css`, with the shared OmniTech palette tokens vendored in.

| Check | Result |
|-------|--------|
| Load `/`, sidebar session list renders via `hx-get` on load | pass |
| Collapse / expand the sidebar from the rail toggle and the header chevron | pass |
| Click a session in the sidebar — chat view swaps in without page reload | pass |
| Dashboard link + a card's "Open" (`/?session=<id>` deep link) both open that consultation | pass |
| Hero composer — typing a request creates a session, runs the loop, and opens the chat view | pass |
| Send a message — `You` / `Consultant` bubbles append (`hx-swap="beforeend"`); recommendation dock refreshes via out-of-band swap | pass |
| Offline path shows an "Offline suggestion" note and still recommends real catalog items | pass |
| Add a preference tag — `"dual screen setup"` stored as `dual-screen-setup`, card re-rendered in place | pass |
| Remove recommendation — inline "Remove this? Remove / Keep" two-step, then `DELETE`; card removed, no native dialog | pass |
| Clear history — inline "Clear all messages? Clear / Cancel" two-step, then `DELETE`; message list emptied | pass |
| Delete consultation — inline "Delete? Yes / No" row in the sidebar item, then `DELETE`; item removed | pass |
| `/dashboard` — past-consultation card grid (title, user, time, counts, Open) and saved-recommendation cards with prices | pass |
| Browser console | no errors |

## 4. Known limitations

* **Offline fallback is keyword-only.** Without Ollama the consultant matches on
  catalog text and category hints; it does not reason about price or trade-offs.
  Category is always correct, but the "best" pick within a category may not
  reflect a stated budget. This path is a graceful degradation, not the intended
  experience.
* **Model quality depends on the pulled model.** The default `qwen2.5:0.5b` is
  small; it occasionally needs the one corrective re-prompt to return valid
  JSON. Larger models remove almost all re-prompts. Only one re-prompt is
  attempted before falling back, to bound latency.
* **Destructive actions use an inline two-step confirm** (a "Delete / Keep" row),
  not the browser's native `confirm()` dialog, which is silently suppressed in
  some embedded webviews.
* **Schema is self-applying.** `get_db()` runs `CREATE TABLE IF NOT EXISTS`
  (the full schema DDL) on every connection, so the service cannot raise
  "no such table" even if the database file is missing, empty, or was written
  by an older build. Startup still seeds demo rows when the tables are empty.
* **SQLite / single writer.** Fine for the assignment and the compose stack; a
  multi-instance deployment would need a server database.
* **Auth is stubbed.** `user_id` defaults to `guest`; there is no session
  ownership enforcement — that belongs to the Users microservice.

## 5. CI evidence

`.github/workflows/student-3.yml` runs on every push/PR touching `student-3/**`:

1. `pip install -r student-3/requirements.txt`
2. `python -m py_compile` for the four backend/database modules
3. `python -m pytest tests/ -v`
4. `docker build -t student-3 ./student-3`

All four steps are green on the `student3-AIConsultation` branch.
