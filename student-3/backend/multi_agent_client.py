"""
Client for the shared Release 2 Multi-Agent Server.

The server (ai-services/multi-agent-server) runs on the PC, not in Docker, like
Ollama, the RAG server and the MCP server. This feature sends it a saved
recommendation plus the customer's requests as evidence; the server runs
Planner -> Worker -> Reviewer and then waits for a human decision
(approve / correct / partial / reject). All agent logic lives in that server -
this module only speaks HTTP to it.
"""

import os
import re

import requests

MULTI_AGENT_HOST = os.getenv("MULTI_AGENT_HOST", "http://localhost:6004").rstrip("/")
# Planner, Worker and Reviewer are three Ollama calls in a row, so allow time.
MULTI_AGENT_TIMEOUT = int(os.getenv("MULTI_AGENT_TIMEOUT", "300"))
STUDENT = "student-3"
WORKFLOW_ID = re.compile(r"^wf-[0-9a-f]{8}$")


class MultiAgentError(Exception):
    """The server answered, but with an error message we can show."""


def _json_or_error(resp):
    body = resp.json()
    if resp.status_code >= 400 and resp.status_code != 503:
        raise MultiAgentError(body.get("error") or f"HTTP {resp.status_code}")
    return body


def start(task, evidence):
    """Start Planner -> Worker -> Reviewer. Returns the workflow dict.

    A 503 means the agents could not reach Ollama; the workflow comes back
    with status "failed" and an "error" field, which callers show as-is.
    Raises requests.RequestException if the server itself is unreachable.
    """
    resp = requests.post(
        f"{MULTI_AGENT_HOST}/workflow/start",
        json={"student": STUDENT, "task": task, "evidence": evidence},
        timeout=MULTI_AGENT_TIMEOUT,
    )
    return _json_or_error(resp)


def decide(workflow_id, decision, reviewer="staff", note="", corrected_answer=""):
    """Send the human decision. Raises MultiAgentError for a rejected request
    (unknown id, missing note / corrected answer, already decided)."""
    resp = requests.post(
        f"{MULTI_AGENT_HOST}/workflow/{workflow_id}/decision",
        json={"decision": decision, "reviewer": reviewer, "note": note,
              "corrected_answer": corrected_answer},
        timeout=30,
    )
    return _json_or_error(resp)


def get(workflow_id):
    resp = requests.get(f"{MULTI_AGENT_HOST}/workflow/{workflow_id}", timeout=10)
    return _json_or_error(resp)


def history(limit=5):
    resp = requests.get(f"{MULTI_AGENT_HOST}/workflows",
                        params={"student": STUDENT, "limit": limit}, timeout=10)
    return _json_or_error(resp)["workflows"]
