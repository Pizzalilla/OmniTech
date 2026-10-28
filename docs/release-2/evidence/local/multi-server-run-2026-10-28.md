# Local multi-server run: Release 2 integrated application

- Date: 2026-10-28 13:33 AEDT · commit c4f96ec · started with `./scripts/start-demo-release2.sh`
- Non-containerised services on the PC: Ollama :11434, RAG :6002, MCP :6003, Multi-Agent :6004
- Docker Compose: home :8080 and student-1 … student-5

## Service status

```
localhost:6002/health  {'chunks_loaded': 56, 'status': 'ok'}
localhost:6003/health  {'examples': {'get_cart': {}, 'get_catalog_product': {'product_id': 1}, 'get_catalog_specifications': {'product_id': 1}, 'get_customer_profile': {'customer_id': 1}, 'get_order_status': {'order_id': 1}, 'get_product_specs': {'product_ids': [511, 512]}, 'get_saved_recommendations': {'session_id': 1}, 'get_warranty_product': {'product_id': 1}}, 'owners': {'get_cart': 'student4', 'get_catalog_product': 'student1', 'get_catalog_specifications': 'student1', 'get_customer_profile': 'student2', 'get_order_status': 'student4', 'get_product_specs': 'student4', 'get_saved_recommendations': 'student3', 'get_warranty_product': 'student5'}, 'services': {'student-1': 'http://localhost:5001', 'student-2': 'http://localhost:5002', 'student-3': 'http://localhost:5003', 'student-4': 'http://localhost:5004', 'student-5': 'http://localhost:5005'}, 'status': 'ok'}
localhost:6004/health  {'agents': ['planner', 'worker', 'reviewer', 'human'], 'decisions': ['approve', 'correct', 'partial', 'reject'], 'model': 'llama3.2', 'ollama_reachable': True}
localhost:11434 Ollama models  ['llama3.2:latest', 'qwen2.5:0.5b', 'llama3.1:8b', 'deepseek-r1:8b']
NAME            STATUS              PORTS
omnitech-home   Up About a minute   0.0.0.0:8080->80/tcp, [::]:8080->80/tcp
student-1       Up About a minute   0.0.0.0:5001->5000/tcp, [::]:5001->5000/tcp
student-2       Up About a minute   0.0.0.0:5002->5000/tcp, [::]:5002->5000/tcp
student-3       Up About a minute   0.0.0.0:5003->5000/tcp, [::]:5003->5000/tcp
student-4       Up About a minute   0.0.0.0:5004->5004/tcp, [::]:5004->5004/tcp
student-5       Up About a minute   0.0.0.0:5005->5000/tcp, [::]:5005->5000/tcp
```

## Multi-Agent review from the Student 3 UI (Docker container → host.docker.internal:6004)

Workflow `wf-9115c0c9`, 19 s from click to result. Screenshot: `local-multi-agent-review-wf-9115c0c9.jpg`.

## Terminal: multi-agent server log (last lines)

```
2026-10-28 13:31:36,195  multi-agent  Multi-Agent server starting on port 6004 (model llama3.2, Ollama http://127.0.0.1:11434)
 * Serving Flask app 'server'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:6004
 * Running on http://192.168.1.104:6004
Press CTRL+C to quit
127.0.0.1 - - [28/Oct/2026 13:31:36] "GET /health HTTP/1.1" 200 -
127.0.0.1 - - [28/Oct/2026 13:32:07] "GET / HTTP/1.1" 404 -
127.0.0.1 - - [28/Oct/2026 13:32:20] "GET /health HTTP/1.1" 200 -
2026-10-28 13:33:04,018  multi-agent  wf-9115c0c9 from student-3 -> awaiting_human
127.0.0.1 - - [28/Oct/2026 13:33:04] "POST /workflow/start HTTP/1.1" 201 -
127.0.0.1 - - [28/Oct/2026 13:33:28] "GET /health HTTP/1.1" 200 -
```

## Terminal: rag server log (last lines)

```
2026-10-28 13:31:36,194  rag  RAG server starting on port 6002 with 56 knowledge chunk(s)
 * Serving Flask app 'server'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:6002
 * Running on http://192.168.1.104:6002
Press CTRL+C to quit
127.0.0.1 - - [28/Oct/2026 13:31:36] "GET /health HTTP/1.1" 200 -
127.0.0.1 - - [28/Oct/2026 13:32:07] "GET / HTTP/1.1" 404 -
127.0.0.1 - - [28/Oct/2026 13:32:20] "GET /health HTTP/1.1" 200 -
2026-10-28 13:32:45,122  rag  RETRIEVE-ONLY 1 chunk(s) confidence=medium for 'I need a laptop that can handle 4K timelines in a video editor.'
127.0.0.1 - - [28/Oct/2026 13:32:45] "POST /rag/retrieve HTTP/1.1" 200 -
127.0.0.1 - - [28/Oct/2026 13:33:28] "GET /health HTTP/1.1" 200 -
```

## Terminal: mcp server log (last lines)

```
2026-10-28 13:31:36,185  mcp  MCP server starting on port 6003 with 8 tool(s): get_cart, get_catalog_product, get_catalog_specifications, get_customer_profile, get_order_status, get_product_specs, get_saved_recommendatio
 * Serving Flask app 'server'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:6003
 * Running on http://192.168.1.104:6003
Press CTRL+C to quit
127.0.0.1 - - [28/Oct/2026 13:31:36] "GET /health HTTP/1.1" 200 -
127.0.0.1 - - [28/Oct/2026 13:32:07] "GET / HTTP/1.1" 404 -
127.0.0.1 - - [28/Oct/2026 13:32:20] "GET /health HTTP/1.1" 200 -
127.0.0.1 - - [28/Oct/2026 13:33:28] "GET /health HTTP/1.1" 200 -
```

## Terminal: Docker Compose, student-3 container (last lines)

```
student-3  | 192.168.65.1 - - [28/Oct/2026 02:32:07] "GET / HTTP/1.1" 200 -
student-3  | 192.168.65.1 - - [28/Oct/2026 02:32:07] "GET / HTTP/1.1" 200 -
student-3  | 192.168.65.1 - - [28/Oct/2026 02:32:20] "GET /api/sessions HTTP/1.1" 200 -
student-3  | 192.168.65.1 - - [28/Oct/2026 02:32:20] "GET /api/sessions/1/recommendations HTTP/1.1" 200 -
student-3  | 192.168.65.1 - - [28/Oct/2026 02:32:32] "GET /?session=1 HTTP/1.1" 200 -
student-3  | 192.168.65.1 - - [28/Oct/2026 02:32:32] "GET /static/style.css HTTP/1.1" 200 -
student-3  | 192.168.65.1 - - [28/Oct/2026 02:32:32] "GET /partials/session-list HTTP/1.1" 200 -
student-3  | 192.168.65.1 - - [28/Oct/2026 02:32:32] "GET /partials/chat/1 HTTP/1.1" 200 -
student-3  | 192.168.65.1 - - [28/Oct/2026 02:32:32] "GET /favicon.ico HTTP/1.1" 404 -
student-3  | 192.168.65.1 - - [28/Oct/2026 02:32:32] "GET /?session=1 HTTP/1.1" 200 -
student-3  | 192.168.65.1 - - [28/Oct/2026 02:32:32] "GET /static/style.css HTTP/1.1" 304 -
student-3  | 192.168.65.1 - - [28/Oct/2026 02:32:32] "GET /favicon.ico HTTP/1.1" 404 -
student-3  | 192.168.65.1 - - [28/Oct/2026 02:32:32] "GET /partials/session-list HTTP/1.1" 200 -
student-3  | 192.168.65.1 - - [28/Oct/2026 02:32:32] "GET /partials/chat/1 HTTP/1.1" 200 -
student-3  | 192.168.65.1 - - [28/Oct/2026 02:33:04] "POST /api/recommendations/1/multi-agent-review HTTP/1.1" 200 -
```
