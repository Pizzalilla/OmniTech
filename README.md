# OmniTech Marketplace

Advanced Software Development Project — Group 36.

An Agentic AI microservices application built with Flask, HTMX, SQLite, and Ollama.

## Repository Structure

```
OmniTech/
├── student-1/ … student-5/   frontend/ backend/ database/ tests/ Dockerfile
├── ai-services/
│   ├── ai-mode/              Release 0 Ollama AI-Mode
│   ├── mcp-server/           Release 1 JSON-RPC tool registry (port 6003)
│   ├── rag-server/           Release 1 retrieval + knowledge/ (port 6002)
│   └── multi-agent-server/   Release 2 Planner, Worker, Reviewer (port 6004)
├── shared/frontend/          Unified home page and shared CSS
├── scripts/deploy/azure/     Azure deploy scripts, gateway and smoke test
├── scripts/test/             Pre-commit security scan scripts
├── .github/workflows/        student-1.yml … student-5.yml, cloud-deployment.yml
├── docs/
│   ├── release-0/            Release 0 report and diagrams
│   ├── release-1/            Release 1 notes
│   ├── release-2/            Cloud docs, diagrams and evidence/
│   └── reports/              Pre- and post-testing reports
├── docker-compose.yml        Home page + the 5 student services
├── README.md
└── .pre-commit-config.yaml, ruff.toml, .secrets.baseline
```

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- [Git](https://git-scm.com/)
- [Ollama](https://ollama.com/) installed and running on your machine
- Python 3.x (for the local MCP, RAG and Multi-Agent servers)

### 1. Clone the Repository

```bash
git clone https://github.com/Pizzalilla/OmniTech.git
cd OmniTech
```

### 2. Start the Local AI Services

AI-Mode (Ollama), the MCP server, the RAG server and the agentic loop run on
your machine, **not** in Docker Compose. Make sure Ollama is running and has a
model:

```bash
ollama pull llama3.2
```

(`ai-services/ai-mode/pull-model.sh qwen2.5` pulls a different model the same way.)

Then start the shared MCP, RAG and Multi-Agent servers, each in its own terminal
(details in each server's README):

```bash
cd ai-services/mcp-server && pip install -r requirements.txt && python server.py
```

```bash
cd ai-services/rag-server && pip install -r requirements.txt && python server.py
```

```bash
cd ai-services/multi-agent-server && pip install -r requirements.txt && python server.py
```

### 3. Build and Run the Containerised Services

```bash
docker compose up --build
```

This starts 6 containers on a shared network (`omnitech-net`). Containers reach
the local AI services through `host.docker.internal`:

| Service        | URL                        | Runs in |
|----------------|----------------------------|---------|
| Home           | http://localhost:8080       | Docker |
| Student 1      | http://localhost:5001       | Docker |
| Student 2      | http://localhost:5002       | Docker |
| Student 3      | http://localhost:5003       | Docker |
| Student 4      | http://localhost:5004       | Docker |
| Student 5      | http://localhost:5005       | Docker |
| Ollama (AI-Mode) | http://localhost:11434    | Local |
| RAG server     | http://localhost:6002       | Local |
| MCP server     | http://localhost:6003       | Local |
| Multi-Agent server | http://localhost:6004   | Local |

On Linux, start Ollama with `OLLAMA_HOST=0.0.0.0 ollama serve` so containers can reach it.

### 4. Open the Home Page

Open [http://localhost:8080](http://localhost:8080). It lists the five student services. The old design-system demo is at [http://localhost:8080/ui-reference.html](http://localhost:8080/ui-reference.html).

## Connecting to Ollama from Your Flask App

Each student container has `OLLAMA_HOST=http://host.docker.internal:11434`, plus
`MCP_HOST`, `RAG_HOST` and `MULTI_AGENT_HOST` for the shared local servers. Use them in your code:

```python
import os, requests

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

response = requests.post(f"{OLLAMA_HOST}/api/generate", json={
    "model": "llama3.2",
    "prompt": "Hello, how can I help?",
    "stream": False,
})
print(response.json()["response"])
```

## Development Workflow

1. Work inside your own `student-N/` directory.
2. Add Python packages to your `student-N/requirements.txt`.
3. Create feature branches: `git checkout -b feature/student-N-description`.
4. Open a Pull Request to `main` when ready for review.
5. CI runs automatically on every push and PR.
6. A commit runs the pre-commit security scans (Ruff security rules, detect-secrets and pip-audit). Set them up once with `pip install -r scripts/test/requirements-security.txt` and `pre-commit install`.

## Cloud deployment

`cloud-deployment.yml` deploys the integrated app to Azure Container Apps after every student workflow passes. AI-Mode, MCP, RAG and the Multi-Agent Server are disabled in that deployment. See `docs/release-2/cloud-deployment.md`.

## Tech Stack

| Layer     | Technology              |
|-----------|-------------------------|
| Backend   | Python 3.x, Flask       |
| Frontend  | HTMX, HTML5, CSS3       |
| Database  | SQLite (per student)    |
| AI Engine | Ollama (local runtime)  |
| DevOps    | Docker, Docker Compose, GitHub Actions |
