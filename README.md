# OmniTech Marketplace

Advanced Software Development Project — Group 36.

An Agentic AI microservices application built with Flask, HTMX, SQLite, and Ollama.

## Repository Structure

```
OmniTech/
├── .github/workflows/   # CI/CD pipeline
├── docs/                 # Project documentation
├── shared/frontend/      # Unified home page and shared CSS
├── student-1/ to student-5/  # Individual microservices
│   ├── app/main.py       # Flask entry point
│   ├── templates/        # Jinja2 / HTMX templates
│   ├── Dockerfile
│   └── requirements.txt
├── ai-services/          # Shared local AI services (not containerised)
│   ├── ai-mode/          # Ollama helpers
│   ├── mcp-server/       # Shared MCP server (port 6003)
│   ├── rag-server/       # Shared RAG server (port 6002)
│   └── multi-agent-server/  # Shared agentic loop (MCP/RAG validation modes)
├── docker-compose.yml    # Home page + the 5 student services
└── .gitignore
```

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- [Git](https://git-scm.com/)
- [Ollama](https://ollama.com/) installed and running on your machine
- Python 3.x (for the local MCP and RAG servers)

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR-ORG/OmniTech.git
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

Then start the shared MCP and RAG servers, each in its own terminal (details in
`ai-services/mcp-server/README.md` and `ai-services/rag-server/README.md`):

```bash
cd ai-services/mcp-server && pip install -r requirements.txt && python server.py
```

```bash
cd ai-services/rag-server && pip install -r requirements.txt && python server.py
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

On Linux, start Ollama with `OLLAMA_HOST=0.0.0.0 ollama serve` so containers can reach it.

### 4. Open the Home Page

Open [http://localhost:8080](http://localhost:8080). It lists the five student services. The old design-system demo is at [http://localhost:8080/ui-reference.html](http://localhost:8080/ui-reference.html).

## Connecting to Ollama from Your Flask App

Each student container has `OLLAMA_HOST=http://host.docker.internal:11434`, plus
`MCP_HOST` and `RAG_HOST` for the shared MCP and RAG servers. Use them in your code:

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

## Tech Stack

| Layer     | Technology              |
|-----------|-------------------------|
| Backend   | Python 3.x, Flask       |
| Frontend  | HTMX, HTML5, CSS3       |
| Database  | SQLite (per student)    |
| AI Engine | Ollama (local runtime)  |
| DevOps    | Docker, Docker Compose, GitHub Actions |
