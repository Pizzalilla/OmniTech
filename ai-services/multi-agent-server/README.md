# Shared Agentic Loop MCP & RAG Validation

## Running it

```bash
docker compose up --build
```
### Start MCP & RAG server
In a new terminal:
```bash
cd ai-services/mcp-server
python3 server.py
```

In another terminal:
```bash
cd ai-services/rag-server
python3 server.py
```

### Terminal Validation
With both MCP and RAG servers running, in a new terminal:
```bash
cd ai-services/multi-agent-server
python3 validate.py --mode rag --question "What is your return policy?"
```

Expected Output: Agentic loop should be approved in 1 attempt where

```bash
python3 validate.py --mode mcp --tool get_order_status --args '{"order_id": 5}'
```

Expected Output: Agentic loop should fail as the order is made up proving the loop can fail.

## Tests
```bash
cd ai-services/multi-agent-server
python3 -m pytest tests/tests.py -v
```