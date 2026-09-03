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

### 2. Build and Run All Services

```bash
docker-compose up --build
```

This starts 6 containers on a shared network (`omnitech-net`):

| Service        | URL                        |
|----------------|----------------------------|
| Student 1      | http://localhost:5001       |
| Student 2      | http://localhost:5002       |
| Student 3      | http://localhost:5003       |
| Student 4      | http://localhost:5014 (UI) / http://localhost:5004 (DB API) |
| Student 5      | http://localhost:5005       |
| Ollama (AI)    | http://localhost:11434      |

### 3. Pull an AI Model

Once the Ollama container is running, pull a model:

```bash
cd ai-services/ai-mode
./pull-model.sh llama3.2
```

Or pull a different model (e.g. `qwen2.5`, `deepseek-r1`):

```bash
./pull-model.sh qwen2.5
```

### 4. Open the Home Page

Open `shared/frontend/index.html` in your browser to see the unified dashboard with links to every microservice.

## Connecting to Ollama from Your Flask App

Each student container has the environment variable `OLLAMA_HOST` set to `http://ollama-service:11434`. Use it in your code:

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
