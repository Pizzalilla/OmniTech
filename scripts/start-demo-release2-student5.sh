#!/usr/bin/env bash
# Start Release 2 shared AI services and the Student 5 Warranty Returns app.
# Run with: ./scripts/start-demo-student5.sh
# Ctrl+C stops the services started by this script.
# Change port to 5005 in student-5/backend/main.py before running.

set -e
cd "$(dirname "$0")/.."

LOGS="${TMPDIR:-/tmp}/omnitech-student5"
mkdir -p "$LOGS"

# Check Ollama is available for the shared AI services.
if ! curl -s -m 3 -o /dev/null http://localhost:11434/api/tags; then
  echo "Ollama isn't running. Open Ollama or run 'ollama serve', then retry."
  exit 1
fi

# Check required ports.
for port in 5005 5006 6002 6003 6004; do
  if lsof -nP -iTCP:$port -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use: $port"
    echo "Stop the existing service before retrying."
    exit 1
  fi
done

# Create a local virtual environment if needed.
if [ ! -f .venv/bin/activate ]; then
  echo "Creating .venv and installing shared dependencies..."
  python3 -m venv .venv
  .venv/bin/pip install -q flask==3.1.* requests==2.33.*
fi

PY="$PWD/.venv/bin/python"

# Stop child processes when the script exits or Ctrl+C is pressed.
trap 'trap - INT TERM EXIT; echo; echo "Stopping demo services..."; kill 0' INT TERM EXIT

# Start shared AI services outside Docker.
$PY ai-services/rag-server/server.py > "$LOGS/rag.log" 2>&1 &
$PY ai-services/mcp-server/server.py > "$LOGS/mcp.log" 2>&1 &
(
  cd ai-services/multi-agent-server
  exec "$PY" server.py
) > "$LOGS/multi-agent.log" 2>&1 &

# Wait for shared services to become ready.
for port in 6002 6003 6004; do
  ready=0
  for _ in $(seq 1 30); do
    if curl -s -m 2 -o /dev/null "http://localhost:$port/health"; then
      ready=1
      break
    fi
    sleep 0.5
  done
  if [ "$ready" -ne 1 ]; then
    echo "Service on port $port did not become ready."
    echo "Check logs in $LOGS"
    exit 1
  fi
done

echo "RAG:         http://localhost:6002/health"
echo "MCP:         http://localhost:6003/health"
echo "Multi-Agent: http://localhost:6004/health"

# Initialise the Student 5 database.
$PY student-5/database/init_db.py > "$LOGS/database-init.log" 2>&1

# Start the Student 5 database service.
$PY student-5/database/app.py > "$LOGS/database.log" 2>&1 &
DB_PID=$!

# Wait for the database service.
db_ready=0
for _ in $(seq 1 30); do
  if curl -s -m 2 -o /dev/null http://localhost:5006/; then
    db_ready=1
    break
  fi
  sleep 0.5
done

if [ "$db_ready" -ne 1 ]; then
  echo "Database service may not expose a / route."
  echo "Check $LOGS/database.log and confirm its health endpoint."
fi

# Start the Student 5 backend.
RAG_ENABLED=false MCP_ENABLED=false \
  PORT=5005 $PY student-5/backend/main.py > "$LOGS/backend.log" 2>&1 &

# Wait for the backend.
backend_ready=0
for _ in $(seq 1 30); do
  if curl -s -m 2 -o /dev/null http://localhost:5005/; then
    backend_ready=1
    break
  fi
  sleep 0.5
done

echo
echo "Student 5 backend: http://localhost:5005"
echo "Logs: $LOGS"
echo "Backend log: $LOGS/backend.log"
echo "Database log: $LOGS/database.log"
echo "Multi-Agent log: $LOGS/multi-agent.log"
echo
echo "Use Ctrl+C to stop the demo."
wait