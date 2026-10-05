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
├── ai-services/ai-mode/  # Ollama AI runtime helpers
├── docker-compose.yml    # Orchestrates all 6 services
└── .gitignore
```

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- [Git](https://git-scm.com/)

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR-ORG/OmniTech.git
cd OmniTech
```

### 2. Start the local AI services (on the PC, not in Docker)

AI-Mode, MCP, RAG and the agentic loop are **not containerised** (Release 1 rule).

1. **Ollama (AI-Mode):** install Ollama, then `ollama pull llama3.2`. It must listen on all
   interfaces so containers can reach it (Windows/macOS app: set `OLLAMA_HOST=0.0.0.0:11434`).
2. **RAG server (port 6002):** `cd ai-services/rag-server && python server.py`
3. **MCP server (port 6003):** `cd ai-services/mcp-server && python server.py`

### 3. Build and Run the Feature Microservices

```bash
docker-compose up --build
```

This starts 6 containers on a shared network (`omnitech-net`):

| Service        | URL                        |
|----------------|----------------------------|
| Home           | http://localhost:8080       |
| Student 1      | http://localhost:5001       |
| Student 2      | http://localhost:5002       |
| Student 3      | http://localhost:5003       |
| Student 4      | http://localhost:5004       |
| Student 5      | http://localhost:5005       |

Every backend gets `OLLAMA_HOST`, `RAG_HOST` and `MCP_HOST` pointing at
`host.docker.internal` (11434 / 6002 / 6003), so the containers use the local AI services above.

### 4. Open the Home Page

Open [http://localhost:8080](http://localhost:8080). It lists the five student services. The old design-system demo is at [http://localhost:8080/ui-reference.html](http://localhost:8080/ui-reference.html).

## Connecting to Ollama from Your Flask App

Each student container has the environment variable `OLLAMA_HOST` set to `http://host.docker.internal:11434` (Ollama on the PC). Use it in your code:

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
