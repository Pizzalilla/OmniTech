#!/usr/bin/env bash
# Release 2 demo in one command: starts the shared RAG, MCP and Multi-Agent servers on this
# PC (not in Docker), then the app with Docker Compose (or just Student 3 with Python if
# Docker isn't running). Ctrl+C stops everything.
#   ./scripts/start-demo-release2.sh
set -e
cd "$(dirname "$0")/.."
LOGS="${TMPDIR:-/tmp}/omnitech-demo"
mkdir -p "$LOGS"

if ! curl -s -m 3 -o /dev/null http://localhost:11434/api/tags; then
  echo "Ollama isn't running. Open the Ollama app (or run 'ollama serve'), then try again."
  exit 1
fi

for port in 5003 6002 6003 6004; do
  if lsof -nP -iTCP:$port -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use. Stop whatever is using it (e.g. 'docker compose down') and try again."
    exit 1
  fi
done

if [ ! -f .venv/bin/activate ]; then
  echo "First run: creating .venv and installing dependencies (takes a minute)..."
  python3 -m venv .venv
  .venv/bin/pip install -q flask==3.1.* requests==2.33.*
fi
PY=.venv/bin/python

trap 'trap - INT TERM EXIT; echo; echo "Stopping..."; kill 0' INT TERM EXIT

$PY ai-services/rag-server/server.py > "$LOGS/rag.log" 2>&1 &
$PY ai-services/mcp-server/server.py > "$LOGS/mcp.log" 2>&1 &
(cd ai-services/multi-agent-server && exec ../../$PY server.py) > "$LOGS/multi-agent.log" 2>&1 &
for port in 6002 6003 6004; do
  for _ in $(seq 1 30); do curl -s -m 2 -o /dev/null "http://localhost:$port/health" && break; sleep 0.5; done
done
echo "RAG server:         http://localhost:6002/health   (log: $LOGS/rag.log)"
echo "MCP server:         http://localhost:6003/health   (log: $LOGS/mcp.log)"
echo "Multi-Agent server: http://localhost:6004/health   (log: $LOGS/multi-agent.log)"
echo "Tip: in another terminal, 'tail -f $LOGS/multi-agent.log' shows the agents working."

if docker info >/dev/null 2>&1; then
  echo
  echo "Starting the app with Docker Compose. When it's up:"
  echo "  Home page              http://localhost:8080"
  echo "  AI Product Consultant  http://localhost:5003/?session=1"
  echo "------------------------------------------------------------"
  docker compose up --build
else
  echo
  echo "Docker isn't running, so starting only Student 3 with Python."
  PORT=5003 $PY student-3/backend/main.py > "$LOGS/student-3.log" 2>&1 &
  for _ in $(seq 1 30); do curl -s -m 2 -o /dev/null http://localhost:5003/ && break; sleep 0.5; done
  echo "  AI Product Consultant  http://localhost:5003/?session=1"
  echo "Showing the Multi-Agent server log below (Ctrl+C stops everything)."
  echo "------------------------------------------------------------"
  tail -n +1 -f "$LOGS/multi-agent.log"
fi
