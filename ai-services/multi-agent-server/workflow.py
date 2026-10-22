"""
Runs one workflow: Planner -> Worker -> Reviewer -> Human Review.

Used by both server.py (HTTP) and cli.py (terminal), so the two always
behave the same way and write to the same history and audit log.
"""

import agents
import audit

MAX_TASK_CHARS = 2000

# what the human picked -> final workflow status
DECISIONS = {
    "approve": "approved",
    "correct": "corrected",
    "partial": "partially_accepted",
    "reject": "rejected",
}


# INPUT CHECKS: raise ValueError with a message the caller can show
def check_start_input(student, task, evidence):
    if not isinstance(student, str) or not student.strip():
        raise ValueError("student is required, e.g. 'student-4'")
    if not isinstance(task, str) or not task.strip():
        raise ValueError("task is required")
    if len(task) > MAX_TASK_CHARS:
        raise ValueError(f"task is too long (max {MAX_TASK_CHARS} characters)")
    if not isinstance(evidence, dict) or not evidence:
        raise ValueError("evidence must be a non-empty JSON object, e.g. {\"cart\": {...}}")


# START: run the three agents and stop at the human step
def start_workflow(student, task, evidence):
    check_start_input(student, task, evidence)
    student, task = student.strip(), task.strip()

    workflow = {
        "id": audit.new_workflow_id(),
        "student": student,
        "task": task,
        "evidence": evidence,
        "status": "running",
        "created_at": audit.now(),
        "plan": None,
        "work": None,
        "review": None,
        "human": None,
        "final_answer": None,
        "error": None,
    }
    wf_id = workflow["id"]
    audit.save_workflow(workflow)
    audit.log_event(wf_id, student, "workflow_started",
                    {"task": task, "evidence": list(evidence.keys())})

    try:
        workflow["plan"] = agents.planner(task, evidence)
        audit.log_event(wf_id, "planner", "plan_created", {
            "steps": len(workflow["plan"]["steps"]),
            "missing_evidence": workflow["plan"]["missing_evidence"],
        })
        audit.save_workflow(workflow)

        workflow["work"] = agents.worker(task, workflow["plan"], evidence)
        audit.log_event(wf_id, "worker", "task_completed", {
            "evidence_used": workflow["work"]["evidence_used"],
            "issues": len(workflow["work"]["issues"]),
        })
        audit.save_workflow(workflow)

        workflow["review"] = agents.reviewer(task, workflow["plan"], evidence, workflow["work"])
        audit.log_event(wf_id, "reviewer", "review_completed", {
            "verdict": workflow["review"]["verdict"],
            "risks": len(workflow["review"]["risks"]),
            "checks": workflow["review"]["checks"],
        })

        workflow["status"] = "awaiting_human"
        audit.log_event(wf_id, "system", "awaiting_human_review")

    except agents.AgentError as exc:
        workflow["status"] = "failed"
        workflow["error"] = str(exc)
        audit.log_event(wf_id, "system", "workflow_failed", {"error": str(exc)})

    audit.save_workflow(workflow)
    return workflow


# HUMAN REVIEW: approve / correct / partial / reject
def apply_decision(workflow_id, decision, reviewer="staff", note="", corrected_answer=""):
    workflow = audit.load_workflow(workflow_id)
    if workflow is None:
        raise LookupError(f"workflow {workflow_id} not found")
    if workflow["status"] != "awaiting_human":
        raise RuntimeError(f"workflow is '{workflow['status']}', not waiting for a human decision")

    decision = (decision or "").strip().lower()
    note = (note or "").strip()
    corrected_answer = (corrected_answer or "").strip()
    reviewer = (reviewer or "staff").strip()[:50]

    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of: {', '.join(DECISIONS)}")
    if decision == "correct" and not corrected_answer:
        raise ValueError("a corrected answer is required when the decision is 'correct'")
    if decision in ("partial", "reject") and not note:
        raise ValueError(f"a note is required when the decision is '{decision}'")

    # what the app should actually use from here on
    if decision == "correct":
        final_answer = corrected_answer
    elif decision == "reject":
        final_answer = None
    else:
        final_answer = workflow["work"]["answer"]

    workflow["human"] = {
        "decision": decision,
        "reviewer": reviewer,
        "note": note,
        "corrected_answer": corrected_answer or None,
        "agreed_with_reviewer": agrees_with_reviewer(decision, workflow["review"]["verdict"]),
        "decided_at": audit.now(),
    }
    workflow["final_answer"] = final_answer
    workflow["status"] = DECISIONS[decision]

    audit.log_event(workflow_id, f"human:{reviewer}", f"decision_{decision}", {
        "note": note,
        "reviewer_verdict": workflow["review"]["verdict"],
        "status": workflow["status"],
    })
    audit.save_workflow(workflow)
    return workflow


# did the human end up where the Reviewer agent pointed? (useful for the report)
def agrees_with_reviewer(decision, verdict):
    if verdict == "pass":
        return decision == "approve"
    if verdict == "fail":
        return decision == "reject"
    return decision in ("correct", "partial")
