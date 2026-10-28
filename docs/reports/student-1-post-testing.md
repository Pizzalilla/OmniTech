# Post-commit CI/CD endpoint testing: Product Catalog (Student 1)

## 1. Summary

| Item | Result |
|---|---|
| Workflow | `.github/workflows/student-1.yml` |
| Trigger | push to `main` or `feature/student-1-**`, pull requests to `main`, manual run, and as a gate inside `cloud-deployment.yml` |
| Endpoint functions tested | `POST /api/products` (create product) and `POST /api/products/<id>/ai-summary` (AI specification summary) |
| Endpoint tests | **5 / 5 passed** (`tests/test_endpoints.py`) |
| Full test suite | **110 / 110 passed** |
| Container smoke test | passed (health, seeded data, AI-off fallback) |
| Evidence run | [student-1 run 40651356561](https://github.com/Pizzalilla/OmniTech/actions/runs/40651356561), push of PR #48 to `main`, 28 Oct 2026 |
| Uploaded results | `student-1-endpoint-tests` artifact (`endpoint-results.xml`, `endpoint-results.txt`) |

## 2. Workflow steps

`student-1.yml` has two jobs. Both ran green on the evidence run.

**validate product catalog sources**

1. Install `student-1/requirements.txt` on Python 3.11.
2. `python -m compileall` for `backend` and `database`.
3. **Endpoint tests**: `pytest tests/test_endpoints.py -v --junitxml=endpoint-results.xml`.
4. Full suite: `pytest -v`.
5. Upload the endpoint results as the `student-1-endpoint-tests` artifact.

**build and smoke test container** (runs after the first job passes)

1. `docker build` the Student 1 image.
2. Start it with `MCP_ENABLED`, `RAG_ENABLED` and `MULTI_AGENT_ENABLED` set to `false`, and Ollama pointed at an unreachable host.
3. Wait for `GET /health`.
4. Check that the seeded `categories` and `products` tables each have at least 10 rows.
5. Check that the AI features fail safely: `/api/multi-agent/history` and `/api/products/1/ai-summary` return 503 while `/api/products` still works.

AI services are off in CI on purpose. This matches the cloud baseline, where AI-Mode, MCP, RAG and the Multi-Agent Server are disabled by default.

## 3. Endpoint test cases

### Endpoint 1: `POST /api/products` (create product)

| Test | What it checks | Result |
|---|---|---|
| `test_create_product_returns_201_and_persists` | A valid product returns 201, and reading it back with `GET /api/products/<id>` returns the same name, brand, price and description | PASSED |
| `test_create_product_rejects_missing_fields` | A body with only a name returns 400 with a "required" error | PASSED |
| `test_create_product_rejects_negative_price` | A negative price returns 400 | PASSED |

### Endpoint 2: `POST /api/products/<id>/ai-summary` (AI specification summary)

| Test | What it checks | Result |
|---|---|---|
| `test_ai_summary_unknown_product` | An unknown product ID returns 404 | PASSED |
| `test_ai_summary_fails_closed_when_ollama_is_down` | When the model cannot be reached, the endpoint returns 503 `"ai summary unavailable"` and the product is still readable | PASSED |

## 4. CI output

Endpoint test step:

```
tests/test_endpoints.py::test_create_product_returns_201_and_persists PASSED [ 20%]
tests/test_endpoints.py::test_create_product_rejects_missing_fields PASSED [ 40%]
tests/test_endpoints.py::test_create_product_rejects_negative_price PASSED [ 60%]
tests/test_endpoints.py::test_ai_summary_unknown_product PASSED          [ 80%]
tests/test_endpoints.py::test_ai_summary_fails_closed_when_ollama_is_down PASSED [100%]
============================== 5 passed in 0.30s ===============================
```

Full suite:

```
============================= 110 passed in 3.11s ==============================
```

Container smoke test:

```
service is healthy
categories rows: 10
products rows: 24
multi-agent history: 503
ai-summary: 503
```

## 5. Known limitations

- **AI summary success path is not tested in CI.** CI has no Ollama, so the AI summary tests cover the unknown-product and model-unavailable paths only. The successful summary is shown in the local deployment evidence and the showcase video, where Ollama is running.
- **Tests use a temporary SQLite database.** Each test gets a fresh seeded database from `tests/conftest.py`, so tests do not affect each other or the real data.
