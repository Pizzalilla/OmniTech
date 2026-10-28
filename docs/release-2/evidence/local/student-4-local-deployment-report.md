# Local deployment report: Student 4 (Cart and Order Processing)

- Date: 2026-10-22
- Branch: syk-student4 (merged to `main` in PR #29)
- Machine: Windows 11, Docker Desktop, Python 3 (`py`)

## What ran

| Service | How it runs | Port | Status |
|---|---|---|---|
| Ollama AI-Mode (`llama3.2`) | Native app on the PC, not in Docker | 11434 | Reachable |
| Shared RAG server | `py ai-services/rag-server/server.py`, not in Docker | 6002 | Running |
| Shared MCP server | `py ai-services/mcp-server/server.py`, not in Docker | 6003 | Running |
| Shared Multi-Agent server | `py ai-services/multi-agent-server/server.py`, not in Docker | 6004 | `/health` 200, `ollama_reachable: true` |
| Student 4 backend + HTMX frontend | `student-4` container in Docker Compose | 5004 | `/api/health` 200, all AI switches on |

In Docker Compose, `student-4` reaches the AI services through `host.docker.internal`
(`OLLAMA_HOST`, `RAG_HOST`, `MCP_HOST`, `MULTI_AGENT_HOST`), so they stay non-containerised.

## Checks (AI on)

| # | Check | Result |
|---|---|---|
| 1 | Open the cart page | Pass; cart, AI helper, MCP, RAG and Cart review cards shown |
| 2 | MCP Order lookup (`get_order_status`, order 1) | Order #1 returned through the MCP tool |
| 3 | RAG Store policy ("What is your return policy?") | Answer with 2 citations |
| 4 | AI helper ("Auto Audit Cart") | Specs via MCP, store policy via RAG, answer `verified` in about 14 s |
| 5 | Orders CRUD (`POST`, `GET`, `PUT`, `DELETE /api/orders`) | 201, 200, 200 (status `Shipped`), 200, then 404 after delete |
| 6 | Multi-Agent review from the UI ("Run review") | 201 in about 27 s; Planner, Worker and Reviewer shown |
| 7 | Evidence sent to the agents | cart, product_specs (MCP), safety_checks, store_policy (RAG) |
| 8 | Human review: **Partial** with no note | Refused with "a note is required", form kept |
| 9 | Human review: **Approve** | Workflow `approved`, final answer shown |
| 10 | Review history ("Recent reviews") | Lists the student-4 workflows from the shared server |
| 11 | Terminal: `py cli.py run`, `list`, `show` | Same workflow from the terminal; `show` prints the audit log |

## Checks (AI services stopped)

Ollama, RAG, MCP and the Multi-Agent server stopped; Docker and the app kept running.

| # | Check | Result |
|---|---|---|
| 12 | Cart, checkout, order history (update, delete) | All working |
| 13 | AI helper | "AI Helper Offline", shows the facts and safety checks from the database |
| 14 | MCP, RAG, Cart review | Each reports its server offline; no crash or hang |

## Checks (cloud mode, `AI_ENABLED=false`)

| # | Check | Result |
|---|---|---|
| 15 | `/api/health` | `ai`: all four switches `false` |
| 16 | AI helper | Answers in about 45 ms with database facts; Ollama not called |
| 17 | MCP, RAG, Cart review | "disabled / turned off in this deployment" in about 5 ms |
| 18 | Orders CRUD | 201, 200, 200, then 404 after delete |

## Multi-Agent workflow record

`docs/release-2/evidence/multi-agent/student-4-workflow-wf-4c850c13.json`: the Reviewer gave
`pass` with the risk "customer may not be aware of the installation requirements"; the human chose
`partial` with a note, so `agreed_with_reviewer` is `false`. Audit: `workflow_started`,
`plan_created`, `task_completed`, `review_completed`, `awaiting_human_review`, `decision_partial`.
