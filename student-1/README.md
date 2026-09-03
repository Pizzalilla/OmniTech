# Product Catalog and Specs

Student 1 service for OmniTech Marketplace. It owns the product catalogue: categories, products, and technical specifications. Other services should read this data through the REST API, not by opening the SQLite file.

Stack: Flask, HTMX, SQLite, Ollama. In Docker Compose it is `student-1` at [http://localhost:5001](http://localhost:5001).

## Run

From the repo root, with Docker Desktop running:

```powershell
docker compose up --build student-1 ollama-service
```

Then pull a model once:

```powershell
docker exec ollama-service ollama pull llama3.2
```

Open [http://localhost:5001](http://localhost:5001). Admin is [http://localhost:5001/admin](http://localhost:5001/admin).

To run the Flask app on the host instead (needs Python 3.11+ and a local Ollama):

```powershell
cd student-1
pip install -r requirements.txt
python backend/app.py
```

That serves on port 5000. Tests use a throwaway database, so they never touch `data/catalog.db`:

```powershell
cd student-1
python -m pytest -q
```

`init_db` seeds the database only when it is empty. To reseed, delete `student-1/data/catalog.db` and restart. Seed data has 10 categories, 12 products, and 36 specifications.

## Pages

| URL | What it is |
|-----|------------|
| `/` | Catalogue with live HTMX filters (category, brand, price, search, spec keyword) |
| `/products/<id>` | Product detail, specs, and shopper AI summary |
| `/admin` | Create, update, and delete products and categories |
| `/admin/products/<id>/specifications` | Spec CRUD for one product, plus admin AI review |

HTMX forms return HTML fragments, not JSON, so the page does not reload on create, update, or delete. The JSON API still exists for other services and for tests.

## REST API

Product list filters (query string): `category_id`, `brand`, `min_price`, `max_price`, `search`, `spec_keyword`.

| Method | Path | Notes |
|--------|------|--------|
| GET | `/health` | `{"status": "ok"}` |
| GET, POST | `/api/categories` | Duplicate names return 409 |
| GET, PUT, DELETE | `/api/categories/<id>` | Delete returns 409 if products still use it |
| GET, POST | `/api/products` | |
| GET, PUT, DELETE | `/api/products/<id>` | Delete also removes that product's specs |
| GET, POST | `/api/products/<id>/specifications` | |
| GET, PUT, DELETE | `/api/products/<id>/specifications/<spec_id>` | 404 if the spec belongs to a different product |
| POST | `/api/products/<id>/ai-summary` | One Ollama paragraph, no review loop |
| POST | `/api/products/<id>/ai-review` | Full Plan → Act → Observe → Adapt loop |

## Agentic loop

`backend/agent.py` is the single entry point. Stages are logged to stdout as `PLAN`, `ACT`, `OBSERVE`, `ADAPT`, `DONE`, so they show up in `docker compose logs student-1`.

1. **Plan** — load the product, category, and stored specs. Flag the same spec name recorded with two different values.
2. **Act** — send those facts to Ollama and ask for a shopper-friendly paragraph.
3. **Observe** — a second Ollama call reviews the paragraph as JSON (`unsupported_claims`, `missing_specifications`). Python also rejects numbers that do not appear in the stored facts.
4. **Adapt** — re-prompt once, naming the claims to drop. If it still fails, the summary is withheld and only the warnings are shown.

Missing specifications are asked on the first review pass and kept even if a rewrite forgets them, because they describe the stored data, not the paragraph.

## Prompt engineering

Prompts live in `backend/ai.py` (`SUMMARY_PROMPT`) and `backend/agent.py` (`REVIEW_PROMPT`, `CORRECTION_TEMPLATE`). Temperature is 0.2 so the model stays close to the supplied facts.

Iterations that changed the prompts:

1. The first summary prompt asked for a shopper-friendly paragraph from the listed specs. A live run on a fridge invented "smart features" that were not in the database.
2. Rules were tightened: use only listed details, never invent a spec or measurement, mention at most three specs, plain prose only.
3. A review prompt was added that must return JSON listing unsupported claims and missing specs. Small models wrapped that JSON in prose, so the review call now sets Ollama `format: "json"`.
4. The correction prompt names the exact rejected claims rather than asking for a generic rewrite. One retry only; a second failure withholds the paragraph.

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_HOST` | `http://localhost:11434` | Compose sets `http://ollama-service:11434` |
| `OLLAMA_MODEL` | `llama3.2` | Must already be pulled |
| `OLLAMA_TIMEOUT` | `60` | Seconds per model call |
| `DATABASE_PATH` | `student-1/data/catalog.db` | Tests override this |
| `HOME_URL` | `http://localhost:8080` | "Back to Home" button |

## Layout notes

`frontend/static/css/styles.css` is a **copy** of `shared/frontend/css/styles.css`. The Docker build context is `./student-1`, so the container cannot reach `../shared`. Page-specific rules sit in template `<style>` blocks so the copy can be refreshed from shared later.

Frontend, backend, and database live in this one Flask container, matching the other student services in this repo.

CI is `.github/workflows/student-1.yml`: pytest, image build, `/health` smoke test, and a check that categories and products each have at least 10 rows.
