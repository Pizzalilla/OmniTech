# Local deployment report: Student 3 (AI Product Consultant)

- Date: 2026-10-20
- Branch: student3-AIConsultation, rebased on `main` at 664cef0
- Machine: macOS (Apple silicon), Python 3.14 venv built from `student-3/requirements.txt`

## What ran

| Service | How it runs | Port | Status |
|---|---|---|---|
| Ollama AI-Mode (`llama3.2`) | Native app on the PC, not in Docker | 11434 | Reachable |
| Shared RAG server | `python ai-services/rag-server/server.py`, not in Docker | 6002 | `/health` 200 |
| Shared Multi-Agent server | `python ai-services/multi-agent-server/server.py`, not in Docker | 6004 | `/health` 200, `ollama_reachable: true` |
| Student 3 backend + HTMX frontend | `python student-3/backend/main.py` (in Compose it is the `student-3` container on 5003) | 5033 | Pages and API 200 |

In Docker Compose, `student-3` reaches these services through `host.docker.internal`
(`OLLAMA_HOST`, `RAG_HOST`, `MCP_HOST`, `MULTI_AGENT_HOST`), so the AI services stay non-containerised.

## Checks

| # | Check | Result |
|---|---|---|
| 1 | Open the consultant UI and a saved consultation | Pass |
| 2 | `POST /api/recommendations/1/multi-agent-review` from the UI ("Review with agents") | 201 in about 15 s; Planner, Worker and Reviewer shown; reviewer verdict `pass` |
| 3 | Evidence sent to the agents | recommendation, customer_requests, other_catalog_matches, store_policy (from the RAG server) |
| 4 | Human review: **Correct** with a corrected recommendation | Workflow `corrected`; the saved recommendation's summary was replaced and tagged `agent-corrected` in the UI straight away |
| 5 | **Review history** | Lists both student-3 workflows from the shared server |
| 6 | Audit log | `workflow_started`, `plan_created`, `task_completed`, `review_completed`, `awaiting_human_review`, `decision_correct` by `human:staff` |
| 7 | Full test suite (`python -m pytest tests/`) | 77 passed |

The full workflow record and audit events are in
`docs/release-2/evidence/multi-agent/student-3-workflow-wf-f3569d0e.json`.

## Observations

- The Reviewer passed the answer but listed "insufficient consideration of budget constraint" as a risk. The human corrected the answer to mention the price, so `agreed_with_reviewer` is `false`. This shows the human step catching something the agents only half-flagged.
- With the Multi-Agent server stopped, the panel shows "The shared Multi-Agent server is not reachable right now." and the rest of the consultant keeps working (covered by `test_review_server_offline`).

## Screenshots to add to the report

1. The review panel showing Planner, Worker and Reviewer with the decision buttons.
2. The recommendation card after the decision, with the `agent-corrected` tag.
3. The terminal running the Multi-Agent server log.
