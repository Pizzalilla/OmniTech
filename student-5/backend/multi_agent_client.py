"""
Client for the shared Release 2 Multi-Agent Server.

All Planner, Worker, Reviewer and audit logic remains in the shared server.
This module only handles HTTP communication.
"""

import os
import re

import requests

MULTI_AGENT_HOST = os.getenv("MULTI_AGENT_HOST", "http://localhost:6004").rstrip("/")
MULTI_AGENT_TIMEOUT = int(os.getenv("MULTI_AGENT_TIMEOUT", "300"))
STUDENT = os.getenv("STUDENT_ID", "student-5")
WORKFLOW_ID = re.compile(r"^wf-[0-9a-f]{8}$")

class MultiAgentError(Exception):
    """The server returned an error response."""

def _json_or_error(resp):
    try:
        body = resp.json()
    except ValueError:
        body = {"error": resp.text or f"HTTP {resp.status_code}"}

    # The server may return 503 with a workflow marked as failed.
    # Preserve that workflow so the caller can display its error.
    if resp.status_code >= 400:
        if resp.status_code == 503 and isinstance(body, dict):
            if body.get("status") == "failed" or body.get("workflow"):
                return body

        if resp.status_code != 503:
            raise MultiAgentError(
                body.get("error", f"HTTP {resp.status_code}")
            )

        raise MultiAgentError(
            body.get("error", "Multi-Agent Server returned HTTP 503")
        )

    return body

def start(task, evidence, student=None):
    """Start Planner -> Worker -> Reviewer and return the server response."""
    resp = requests.post(
        f"{MULTI_AGENT_HOST}/workflow/start",
        json={
            "student": student or STUDENT,
            "task": task,
            "evidence": evidence,
        },
        timeout=MULTI_AGENT_TIMEOUT,
    )
    return _json_or_error(resp)

def decide(
    workflow_id,
    decision,
    reviewer="staff",
    note="",
    corrected_answer="",
):
    """Submit the human decision for a workflow."""
    if not WORKFLOW_ID.fullmatch(workflow_id or ""):
        raise ValueError("Invalid Multi-Agent workflow ID.")

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
    """Retrieve a workflow and its audit information."""
    if not WORKFLOW_ID.fullmatch(workflow_id or ""):
        raise ValueError("Invalid Multi-Agent workflow ID.")

    resp = requests.get(
        f"{MULTI_AGENT_HOST}/workflow/{workflow_id}",
        timeout=10,
    )
    return _json_or_error(resp)

def history(limit=5, student=None):
    """Return workflow history for a student."""
    resp = requests.get(
        f"{MULTI_AGENT_HOST}/workflows",
        params={
            "student": student or STUDENT,
            "limit": limit,
        },
        timeout=10,
    )
    return _json_or_error(resp)["workflows"]
