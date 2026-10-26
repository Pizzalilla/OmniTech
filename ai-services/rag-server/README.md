# Shared RAG Server (Release 1)

One shared, **non-containerised** RAG server that runs locally and is used by
every student feature's backend/API - the same way `OLLAMA_HOST` is already
used for the local AI-Mode. It retrieves relevant context from local
knowledge documents and asks Ollama to generate a grounded answer with
citations and a confidence category, or reports insufficient context instead
of guessing.

## Running it

```bash
cd ai-services/rag-server
pip install -r requirements.txt
python server.py
```

Runs on `http://localhost:6002` by default. Requires Ollama running locally
(`OLLAMA_HOST`, default `http://localhost:11434`) for generation - retrieval
and the insufficient-context path work even if Ollama is down.

Env vars (all optional):

| Var | Default | Purpose |
|-----|---------|---------|
| `RAG_PORT` | `6002` | Port the server listens on |
| `RAG_TOP_K` | `4` | Max number of context chunks retrieved per query |
| `OLLAMA_HOST` | `http://localhost:11434` | Shared local Ollama instance |
| `OLLAMA_MODEL` | `llama3.2` | Model used for generation |
| `OLLAMA_TIMEOUT` | `120` | Request timeout in seconds |

### How Docker containers reach it

The RAG server is **not** a Docker Compose service - it runs on the PC like
Ollama. `docker-compose.yml` gives every student container
`RAG_HOST=http://host.docker.internal:6002`, so in your backend use:

```python
RAG_HOST = os.getenv("RAG_HOST", "http://localhost:6002")
```

## Calling it from your feature's backend

Add `RAG_HOST` (e.g. `http://localhost:6002`, or `http://host.docker.internal:6002`
from inside a container - TBC once the docker-compose wiring ticket lands) to
your backend's env, then call it like any other HTTP dependency:

```python
import requests
resp = requests.post(f"{RAG_HOST}/rag/query", json={"query": user_message}, timeout=125)
data = resp.json()
```

### `POST /rag/query`

Request:
```json
{ "query": "What is your return policy?" }
```

Response (context found):
```json
{
  "answer": "Items can be returned within 30 days of delivery for a full refund...",
  "citations": [
    { "source": "shipping-and-returns.md", "section": "Return Window", "snippet": "Items can be returned within 30 days..." }
  ],
  "confidence": "high"
}
```

Response (nothing relevant found - display this instead of an unsupported answer):
```json
{ "insufficient_context": true, "message": "I don't have enough information to answer that yet." }
```

`confidence` is `"high"`, `"medium"`, or `"low"`, based on how strongly the
retrieved context matched the query. If Ollama is unreachable, the answer
falls back to a deterministic excerpt from the top-matching chunk and
`confidence` is forced to `"low"` rather than failing the request.

### `POST /rag/retrieve`

Retrieval only - returns the matching knowledge sections **without** calling
Ollama. Use this when your backend builds its own grounded prompt (e.g. it
also adds facts from its own database) so you don't pay for two LLM calls.

Request:
```json
{ "query": "can I run a microwave and air fryer on one power point", "limit": 3 }
```

Response:
```json
{
  "chunks": [
    { "source": "appliance-installation-and-cart.md", "heading": "Running Kitchen Appliances Together", "text": "..." }
  ],
  "confidence": "high",
  "insufficient_context": false
}
```

### `GET /health`

Returns `{"status": "ok", "chunks_loaded": <int>}` - useful for confirming
the server is up and the knowledge base loaded before running validation.

## Adding your own feature's knowledge

The corpus lives in `knowledge/*.md`. Each file needs one `# Title` line and
one or more `## Section` headings - every section becomes a separately
citable chunk. If your feature has domain knowledge worth grounding answers
in (policies, FAQs, product data), add a new markdown file here rather than
routing it through your own service - that keeps the RAG server's knowledge
genuinely shared.

## Terminal validation

```bash
python query.py "What is your return policy?"
```

Prints the raw JSON response - use this to capture terminal validation
evidence for the report.

## Tests

```bash
cd ai-services/rag-server
python -m pytest tests/ -v
```

Tests never call a live Ollama instance - `server.generate` is monkeypatched
in tests that need to control the generated answer, matching the same
isolation approach used in student-3's test suite.
