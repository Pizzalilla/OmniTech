"""
Planner, Worker and Reviewer agents.

Each agent sends one prompt to local Ollama and gets one JSON object back.
The agents never fetch data themselves - the student backend that starts
the workflow passes in the evidence (cart, order, specs, RAG text, ...),
so the same server works for every student's feature.
"""

import json
import os

import requests

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
# if not OLLAMA_HOST.startswith("http"):
#     OLLAMA_HOST = f"http://{OLLAMA_HOST}"
# if "0.0.0.0" in OLLAMA_HOST:  # noqa: S104
#     OLLAMA_HOST = OLLAMA_HOST.replace("0.0.0.0", "localhost")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

# keeps prompts a sensible size for a small local model
MAX_EVIDENCE_CHARS = int(os.getenv("MAX_EVIDENCE_CHARS", "6000"))

VERDICTS = ("pass", "needs_changes", "fail")


class AgentError(Exception):
    """Ollama is down, timed out, or sent back something unusable."""


# OLLAMA: one chat call, JSON mode
def ask_ollama(system_prompt, user_prompt):
    try:
        resp = requests.post(
            f"{OLLAMA_HOST.rstrip('/')}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        text = resp.json()["message"]["content"]
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise AgentError(f"Ollama call failed: {exc}") from exc
    return parse_json(text)


# PARSE: the model sometimes wraps the JSON in extra text, so cut out the {...}
def parse_json(text):
    text = text or ""
    try:
        data = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise AgentError("agent reply was not JSON") from None
        try:
            data = json.loads(text[start:end + 1])
        except ValueError:
            raise AgentError("agent reply was not JSON") from None
    if not isinstance(data, dict):
        raise AgentError("agent reply was not a JSON object")
    return data


# HELPERS: tidy up whatever the model returned
def as_list(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if value:
        return [str(value).strip()]
    return []


def as_text(value, default=""):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value).strip() or default


def evidence_text(evidence):
    text = json.dumps(evidence, indent=2, default=str)
    if len(text) > MAX_EVIDENCE_CHARS:
        text = text[:MAX_EVIDENCE_CHARS] + "\n... (evidence cut short)"
    return text


# ---------------------------------------------------------------------------
# PLANNER
# ---------------------------------------------------------------------------

PLANNER_PROMPT = (
    "You are the Planner agent for the OmniTech store. You do not answer the task. "
    "You write a short plan another agent will follow. Only plan with the evidence "
    "names you are given. Reply with JSON only:\n"
    '{"goal": "one sentence", "steps": ["step 1", "step 2"], '
    '"evidence_needed": ["evidence name"], "success_criteria": ["what a good answer must do"]}'
)


# PLANNER: task + evidence names -> plan
def planner(task, evidence):
    names = ", ".join(evidence.keys()) or "none"
    prompt = f"TASK:\n{task}\n\nEVIDENCE AVAILABLE: {names}\n\nWrite the plan (3 to 5 steps)."
    raw = ask_ollama(PLANNER_PROMPT, prompt)

    plan = {
        "goal": as_text(raw.get("goal"), task),
        "steps": as_list(raw.get("steps")),
        "evidence_needed": as_list(raw.get("evidence_needed")),
        "success_criteria": as_list(raw.get("success_criteria")),
    }
    if not plan["steps"]:
        raise AgentError("planner returned no steps")

    # anything the plan wants that the backend didn't send
    plan["missing_evidence"] = [e for e in plan["evidence_needed"] if e not in evidence]
    return plan


# ---------------------------------------------------------------------------
# WORKER
# ---------------------------------------------------------------------------

WORKER_PROMPT = (
    "You are the Worker agent for the OmniTech store. Follow the plan step by step and "
    "complete the task using ONLY the evidence given. Never invent prices, numbers, "
    "stock or policies. If the evidence is not enough, say so in issues. Reply with JSON only:\n"
    '{"answer": "your answer for the customer or staff member", '
    '"steps_done": ["what you did for each plan step"], '
    '"evidence_used": ["evidence name"], "issues": ["anything you could not do"]}'
)


# WORKER: follow the plan using the supplied evidence
def worker(task, plan, evidence):
    prompt = (
        f"TASK:\n{task}\n\n"
        f"PLAN:\n{json.dumps(plan['steps'], indent=2)}\n\n"
        f"EVIDENCE:\n{evidence_text(evidence)}"
    )
    raw = ask_ollama(WORKER_PROMPT, prompt)

    work = {
        "answer": as_text(raw.get("answer")),
        "steps_done": as_list(raw.get("steps_done")),
        "evidence_used": as_list(raw.get("evidence_used")),
        "issues": as_list(raw.get("issues")),
    }
    if not work["answer"]:
        raise AgentError("worker returned an empty answer")
    return work


# ---------------------------------------------------------------------------
# REVIEWER
# ---------------------------------------------------------------------------

REVIEWER_PROMPT = (
    "You are the Reviewer agent for the OmniTech store. Check the Worker's answer "
    "against the plan and the evidence. Point out anything not supported by the evidence, "
    "any plan step that was skipped, and any risk to the customer or the business. "
    "Reply with JSON only:\n"
    '{"verdict": "pass" or "needs_changes" or "fail", '
    '"summary": "one or two sentences", "risks": ["risk"], '
    '"recommendations": ["what to change or check"]}'
)


# REVIEWER: check the worker's output, plus a couple of checks done in code
def reviewer(task, plan, evidence, work):
    prompt = (
        f"TASK:\n{task}\n\n"
        f"PLAN:\n{json.dumps(plan, indent=2)}\n\n"
        f"EVIDENCE:\n{evidence_text(evidence)}\n\n"
        f"WORKER OUTPUT:\n{json.dumps(work, indent=2)}"
    )
    raw = ask_ollama(REVIEWER_PROMPT, prompt)

    verdict = as_text(raw.get("verdict")).lower().replace(" ", "_")
    if verdict not in VERDICTS:
        verdict = "needs_changes"

    review = {
        "verdict": verdict,
        "summary": as_text(raw.get("summary"), "No summary given."),
        "risks": as_list(raw.get("risks")),
        "recommendations": as_list(raw.get("recommendations")),
        "checks": [],
    }

    # code checks - these don't depend on the model getting it right
    unknown = [e for e in work["evidence_used"] if e not in evidence]
    if unknown:
        review["checks"].append(f"Worker cited evidence that was never supplied: {', '.join(unknown)}")
    if plan.get("missing_evidence"):
        review["checks"].append(f"Plan asked for evidence the backend didn't send: {', '.join(plan['missing_evidence'])}")
    if work["issues"]:
        review["checks"].append(f"Worker reported {len(work['issues'])} issue(s)")

    # citing made-up evidence can't be a pass - send it to the human as needs_changes
    if unknown and verdict == "pass":
        review["verdict"] = "needs_changes"
    return review
