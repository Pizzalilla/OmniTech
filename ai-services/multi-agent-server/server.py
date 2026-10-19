"""
Shared Multi-Agent Server for OmniTech Release 2.

Runs on the PC (not in Docker), same as Ollama, the RAG server and the MCP
server. A student backend sends a task plus its own evidence, the server
runs Planner -> Worker -> Reviewer, then waits for a human decision.

Endpoints:
    GET  /health                       status, model, whether Ollama is reachable
    POST /workflow/start               {"student", "task", "evidence"}  -> 201 awaiting_human
    POST /workflow/<id>/decision       {"decision", "reviewer", "note", "corrected_answer"}
    GET  /workflow/<id>                one workflow plus its audit events
    GET  /workflows?student=student-4  workflow history (newest first)
    GET  /audit?workflow_id=wf-...     raw audit log events

Run directly:
    python server.py        -> http://localhost:6004
"""

import logging
import os

import requests
from flask import Flask, jsonify, request

import agents
import audit
import workflow as wf

MULTI_AGENT_PORT = int(os.getenv("MULTI_AGENT_PORT", "6004"))
# 0.0.0.0 so the student containers can reach us through host.docker.internal
MULTI_AGENT_BIND = os.getenv("MULTI_AGENT_BIND", "0.0.0.0")  # noqa: S104

log = logging.getLogger("multi-agent")
if not log.handlers:
    log.setLevel(logging.INFO)
    log.addHandler(logging.StreamHandler())
for _h in log.handlers:
    _h.setFormatter(logging.Formatter("%(asctime)s  multi-agent  %(message)s"))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024  # 1 MB is plenty for evidence


# SHORT VIEW: what the history list shows for each workflow
def summary(item):
    review = item.get("review") or {}
    human = item.get("human") or {}
    return {
        "id": item["id"],
        "student": item.get("student"),
        "task": item.get("task"),
        "status": item.get("status"),
        "reviewer_verdict": review.get("verdict"),
        "human_decision": human.get("decision"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }


def ollama_up():
    try:
        return requests.get(f"{agents.OLLAMA_HOST.rstrip('/')}/api/tags", timeout=2).ok
    except requests.RequestException:
        return False


# HEALTH
@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "multi-agent-server",
        "port": MULTI_AGENT_PORT,
        "model": agents.OLLAMA_MODEL,
        "ollama_reachable": ollama_up(),
        "agents": ["planner", "worker", "reviewer", "human"],
        "decisions": list(wf.DECISIONS),
    })


# START: run planner, worker and reviewer
@app.post("/workflow/start")
def start():
    body = request.get_json(silent=True) or {}
    try:
        result = wf.start_workflow(body.get("student"), body.get("task"), body.get("evidence"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    log.info("%s from %s -> %s", result["id"], result["student"], result["status"])
    if result["status"] == "failed":
        # usually Ollama isn't running - the backend should show a friendly message
        return jsonify(result), 503
    return jsonify(result), 201


# HUMAN DECISION
@app.post("/workflow/<workflow_id>/decision")
def decision(workflow_id):
    body = request.get_json(silent=True) or {}
    try:
        result = wf.apply_decision(
            workflow_id,
            body.get("decision"),
            reviewer=body.get("reviewer", "staff"),
            note=body.get("note", ""),
            corrected_answer=body.get("corrected_answer", ""),
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 409
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    log.info("%s human decision: %s", workflow_id, result["human"]["decision"])
    return jsonify(result)


# ONE WORKFLOW + its audit trail
@app.get("/workflow/<workflow_id>")
def get_workflow(workflow_id):
    item = audit.load_workflow(workflow_id)
    if item is None:
        return jsonify({"error": f"workflow {workflow_id} not found"}), 404
    item["events"] = audit.read_events(workflow_id)
    return jsonify(item)


# HISTORY
@app.get("/workflows")
def list_workflows():
    student = request.args.get("student") or None
    limit = min(request.args.get("limit", 20, type=int) or 20, 200)
    items = audit.list_workflows(student)
    return jsonify({"count": len(items), "workflows": [summary(i) for i in items[:limit]]})


# RAW AUDIT LOG (last 200 events)
@app.get("/audit")
def audit_log():
    workflow_id = request.args.get("workflow_id") or None
    events = audit.read_events(workflow_id)
    return jsonify({"count": len(events), "events": events[-200:]})


if __name__ == "__main__":
    log.info("Multi-Agent server starting on port %d (model %s, Ollama %s)",
             MULTI_AGENT_PORT, agents.OLLAMA_MODEL, agents.OLLAMA_HOST)
    app.run(host=MULTI_AGENT_BIND, port=MULTI_AGENT_PORT, threaded=True)
