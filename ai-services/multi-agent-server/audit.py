"""
Audit log and workflow history for the Multi-Agent Server.

logs/audit.jsonl    one line per event (who did what, and when)
logs/history/       one JSON file per workflow (plan, work, review, decision)
"""

import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = Path(os.getenv("MULTI_AGENT_LOG_DIR", str(BASE_DIR / "logs")))
AUDIT_FILE = LOG_DIR / "audit.jsonl"
HISTORY_DIR = LOG_DIR / "history"

# workflow ids always look like wf-1a2b3c4d
ID_PATTERN = re.compile(r"^wf-[0-9a-f]{8}$")

_lock = threading.Lock()


# TIME: current UTC time as text
def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# NEW ID: short random workflow id
def new_workflow_id():
    return "wf-" + uuid.uuid4().hex[:8]


def valid_id(workflow_id):
    return bool(ID_PATTERN.match(workflow_id or ""))


# AUDIT LOG: append one event, old lines are never changed
def log_event(workflow_id, actor, action, detail=None):
    event = {
        "time": now(),
        "workflow_id": workflow_id,
        "actor": actor,
        "action": action,
        "detail": detail or {},
    }
    with _lock:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    return event


# READ AUDIT LOG: everything, or only one workflow
def read_events(workflow_id=None):
    if not AUDIT_FILE.exists():
        return []
    events = []
    with open(AUDIT_FILE, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            event = json.loads(line)
            if workflow_id is None or event.get("workflow_id") == workflow_id:
                events.append(event)
    return events


# SAVE WORKFLOW: overwrite history/<id>.json with the latest state
def save_workflow(workflow):
    workflow["updated_at"] = now()
    with _lock:
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_DIR / f"{workflow['id']}.json", "w", encoding="utf-8") as f:
            json.dump(workflow, f, indent=2)


# LOAD WORKFLOW: None if the id is bad or the file isn't there
# (the id comes from a URL, so it's checked before it touches the file system)
def load_workflow(workflow_id):
    if not valid_id(workflow_id):
        return None
    path = HISTORY_DIR / f"{workflow_id}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# LIST WORKFLOWS: newest first, optionally only one student's
def list_workflows(student=None):
    if not HISTORY_DIR.exists():
        return []
    items = []
    for path in HISTORY_DIR.glob("wf-*.json"):
        with open(path, encoding="utf-8") as f:
            workflow = json.load(f)
        if student is None or workflow.get("student") == student:
            items.append(workflow)
    items.sort(key=lambda w: w.get("created_at", ""), reverse=True)
    return items
