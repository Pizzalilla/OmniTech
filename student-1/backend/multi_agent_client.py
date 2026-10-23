import os
import re

import requests

MULTI_AGENT_HOST = os.getenv("MULTI_AGENT_HOST", "http://localhost:6004").rstrip("/")
# three Ollama calls (planner, worker, reviewer) run before this returns
MULTI_AGENT_TIMEOUT = int(os.getenv("MULTI_AGENT_TIMEOUT", "300"))
STUDENT = "student-1"
WORKFLOW_ID = re.compile(r"^wf-[0-9a-f]{8}$")


class MultiAgentError(Exception):
    pass


def _json_or_error(resp):
    body = resp.json()
    # 503 still returns the workflow, with status "failed" when Ollama is down
    if resp.status_code >= 400 and resp.status_code != 503:
        raise MultiAgentError(body.get("error") or f"HTTP {resp.status_code}")
    return body


def start(task, evidence):
    resp = requests.post(
        f"{MULTI_AGENT_HOST}/workflow/start",
        json={"student": STUDENT, "task": task, "evidence": evidence},
        timeout=MULTI_AGENT_TIMEOUT,
    )
    return _json_or_error(resp)


def decide(workflow_id, decision, reviewer="staff", note="", corrected_answer=""):
    resp = requests.post(
        f"{MULTI_AGENT_HOST}/workflow/{workflow_id}/decision",
        json={
            "decision": decision,
            "reviewer": reviewer,
            "note": note,
            "corrected_answer": corrected_answer,
        },
        timeout=30,
    )
    return _json_or_error(resp)


def get(workflow_id):
    resp = requests.get(f"{MULTI_AGENT_HOST}/workflow/{workflow_id}", timeout=10)
    return _json_or_error(resp)


def history(limit=5):
    resp = requests.get(
        f"{MULTI_AGENT_HOST}/workflows",
        params={"student": STUDENT, "limit": limit},
        timeout=10,
    )
    return _json_or_error(resp)["workflows"]
