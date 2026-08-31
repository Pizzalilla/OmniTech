"""
Agentic consultation loop for the AI Product Consultant.

    Plan     Search the catalog with the whole recent conversation and take the
             relevant shortlist - only those products are shown to the model.
    Act      Send a structured, contextual prompt to the local Ollama API.
    Observe   Validate the output: well-formed JSON, and every recommended id is
              in the shortlist (a real product from the wrong category is
              rejected just like an invented id).
    Adapt     On failure, send one corrective re-prompt naming the exact
              problems and re-validate. If it still fails, or Ollama cannot be
              reached, fall back to a deterministic catalog match on the same
              conversation context so the answer stays on-topic.

`run_consultation()` is the single entry point used by the Flask layer and never
raises - callers always receive a usable dict.
"""

import json
import logging
import os
import re

import requests

import catalog

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
MAX_REPROMPTS = 1

# Every stage of the loop is logged here. See it on the server's stdout, or set
# CONSULTANT_LOG=/path/to/agent.log to also write it to a file.
log = logging.getLogger("consultant.agent")
if not log.handlers:
    log.setLevel(logging.INFO)
    log.addHandler(logging.StreamHandler())
    _logfile = os.getenv("CONSULTANT_LOG")
    if _logfile:
        log.addHandler(logging.FileHandler(_logfile))
for _h in log.handlers:
    _h.setFormatter(logging.Formatter("%(asctime)s  agent  %(message)s"))

SYSTEM_INSTRUCTIONS = (
    "You are the OmniTech Marketplace AI Product Consultant for consumer "
    "electronics. Recommend the best products for the customer's stated needs, "
    "budget and preferences.\n"
    "Rules:\n"
    "1. Recommend ONLY products from the PRODUCT CATALOG below.\n"
    "2. Put the exact catalog id of every product you recommend in "
    "recommended_product_ids, and also mention it in reply.\n"
    "3. Recommend only products whose id appears in the PRODUCT CATALOG below. "
    "Do not recommend anything from another category. Never invent ids and "
    'never write "ID" literally.\n'
    "4. Answer with ONE JSON object and nothing else. Keys: reply (string), "
    "recommended_product_ids (array of catalog id strings), summary (string).\n"
    "5. recommended_product_ids may be empty only when you ask a clarifying "
    "question - put that question in reply.\n"
    "\n"
    "The JSON shape (the ids here are placeholders - use the real ids from the "
    "catalog above):\n"
    '{"reply": "The <product name> (<its id>) fits because ...", '
    '"recommended_product_ids": ["<its id>"], "summary": "<why it fits>"}'
)


# --------------------------------------------------------------------------- #
# Plan
# --------------------------------------------------------------------------- #
def _context_query(user_message, history):
    """Build the catalog search string from the recent *user* turns, so a
    follow-up like "music in the gym" still carries the earlier "headphones"."""
    turns = [t["message_text"] for t in (history or []) if t.get("sender") == "user"]
    if user_message and (not turns or turns[-1] != user_message):
        turns.append(user_message)
    return " ".join(turns[-5:]) or (user_message or "")


def plan(user_message, history=None):
    """Retrieve the slice of the catalog relevant to the request. Only these
    products are shown to the model and only these may be recommended."""
    query = _context_query(user_message, history)
    relevant = catalog.search(query)
    return {
        "query": query,
        "relevant_products": relevant,
        "relevant_ids": [p["id"] for p in relevant],
        "catalog_block": catalog.context_block(relevant),
        "valid_ids": sorted(catalog.VALID_IDS),
    }


def _build_prompt(plan_ctx, history, user_message, correction=None):
    lines = [
        SYSTEM_INSTRUCTIONS,
        "",
        "PRODUCT CATALOG (recommend only from this list):",
        plan_ctx["catalog_block"],
        "",
    ]
    if history:
        lines.append("CONVERSATION SO FAR:")
        for turn in history[-6:]:
            who = "Customer" if turn["sender"] == "user" else "Consultant"
            lines.append(f"{who}: {turn['message_text']}")
        lines.append("")
    lines.append(f"Customer: {user_message}")
    if correction:
        lines.append("")
        lines.append(f"Your previous answer was rejected by the validator: {correction}")
        lines.append("Return a corrected JSON object that fixes every problem.")
    lines.append("")
    lines.append(
        "Answer with one JSON object. recommended_product_ids must contain only "
        "ids from the catalog above (" + ", ".join(plan_ctx["relevant_ids"]) + ")."
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Act
# --------------------------------------------------------------------------- #
def act(prompt):
    """POST a prompt to Ollama and return the raw completion text.

    Raises requests.RequestException if the service cannot be reached.
    """
    resp = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.3},
        },
        timeout=OLLAMA_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("response", "")


# --------------------------------------------------------------------------- #
# Observe
# --------------------------------------------------------------------------- #
def _extract_json(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except ValueError:
            return None
    return None


_PLACEHOLDERS = {"ID", "<ID>", "<ITS ID>", "XXX", "XXX-000"}


def observe(raw_text, allowed_ids):
    """Validate a raw completion.

    `allowed_ids` is the shortlist of catalog ids that were shown to the model
    for this request. The answer may recommend ONLY from that set - a real
    product from the wrong category is rejected just like an invented id.

    Returns (ok, data, issues). `data` is a normalised dict (or None if the
    output was not JSON at all); `issues` lists the problems found.
    """
    issues = []
    data = _extract_json(raw_text)
    if data is None:
        return False, None, ["output was not valid JSON in the required shape"]

    allowed_ids = set(allowed_ids)
    reply = str(data.get("reply", "")).strip()
    summary = str(data.get("summary", "")).strip()
    ids = data.get("recommended_product_ids", [])
    if not isinstance(ids, list):
        issues.append("recommended_product_ids must be a list of id strings")
        ids = []
    ids = [str(i).strip() for i in ids]

    if not reply:
        issues.append("the 'reply' field is missing or empty")

    # Final set: allowed ids from the list, plus allowed ids the model named in
    # the reply prose (mentioning one counts as recommending it).
    listed = [i for i in ids if i in allowed_ids]
    named = [i for i in sorted(allowed_ids) if i in reply]
    final_ids = list(dict.fromkeys(listed + named))

    # Anything in the list that is not allowed and is not an obvious template
    # placeholder is a hard error - it forces a corrective re-prompt.
    bad = [
        i for i in ids
        if i not in allowed_ids and i.upper() not in _PLACEHOLDERS
    ]
    if bad:
        if any(i in catalog.VALID_IDS for i in bad):
            issues.append(
                "recommended " + ", ".join(bad)
                + " - not among the products shown for this request; recommend "
                "only from " + ", ".join(sorted(allowed_ids))
            )
        else:
            issues.append("these product ids are not in the catalog: " + ", ".join(bad))

    if not final_ids and "?" not in reply:
        issues.append("no catalog products were recommended")

    if not summary:
        summary = reply[:200]

    clean = {
        "reply": reply,
        "recommended_product_ids": final_ids,
        "summary": summary,
    }
    return (len(issues) == 0), clean, issues


# --------------------------------------------------------------------------- #
# Fallback
# --------------------------------------------------------------------------- #
def _fallback(query):
    picks = catalog.search(query, limit=3)[:2]
    ids = [p["id"] for p in picks]
    if picks:
        bullets = "; ".join(
            f"{p['name']} ({p['id']}, ${p['price']})" for p in picks
        )
        reply = (
            "Our AI consultant is offline right now, but based on your request "
            f"these catalog items look like the closest fit: {bullets}. "
            + " ".join(p["description"] for p in picks)
        )
        summary = "Offline keyword match: " + ", ".join(p["name"] for p in picks)
    else:
        reply = "Our AI consultant is offline right now. Please try again shortly."
        summary = ""
    return {"reply": reply, "recommended_product_ids": ids, "summary": summary}


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run_consultation(user_message, history=None):
    """Execute Plan -> Act -> Observe -> Adapt and return the final answer.

    Result dict:
        reply                    str
        recommended_product_ids  list[str]  (validated against the catalog)
        summary                  str
        meta = {
            attempts       int   number of model calls made
            reprompts      int   number of corrective re-prompts
            used_fallback  bool
            stage          str   last stage reached
            issues         list  validation issues on the final answer
        }
    """
    history = history or []
    log.info("PLAN   query=%r", user_message[:120])
    plan_ctx = plan(user_message, history)
    allowed_ids = set(plan_ctx["relevant_ids"])
    fallback_query = plan_ctx["query"]
    log.info("PLAN   %d relevant catalog items (recommend only these): %s",
             len(plan_ctx["relevant_ids"]), plan_ctx["relevant_ids"])
    meta = {
        "attempts": 0, "reprompts": 0, "used_fallback": False,
        "stage": "plan", "issues": [],
    }

    # Act
    try:
        meta["attempts"] += 1
        meta["stage"] = "act"
        log.info("ACT    calling ollama model=%s (attempt 1)", OLLAMA_MODEL)
        raw = act(_build_prompt(plan_ctx, history, user_message))
    except requests.RequestException as exc:
        log.warning("ACT    ollama unreachable (%s) -> catalog fallback", exc)
        meta.update(used_fallback=True, stage="fallback",
                    issues=[f"ollama unreachable: {exc}"])
        result = _fallback(fallback_query)
        result["meta"] = meta
        return result

    # Observe
    meta["stage"] = "observe"
    ok, data, issues = observe(raw, allowed_ids)
    log.info("OBSERVE ok=%s ids=%s issues=%s",
             ok, data["recommended_product_ids"] if data else None, issues)

    # Adapt
    while not ok and meta["reprompts"] < MAX_REPROMPTS:
        meta["reprompts"] += 1
        meta["stage"] = "adapt"
        log.info("ADAPT  re-prompting (attempt %d) with: %s",
                 meta["attempts"] + 1, "; ".join(issues))
        try:
            meta["attempts"] += 1
            raw = act(
                _build_prompt(
                    plan_ctx, history, user_message,
                    correction="; ".join(issues),
                )
            )
        except requests.RequestException as exc:
            issues.append(f"re-prompt failed: {exc}")
            break
        ok, data, issues = observe(raw, allowed_ids)
        log.info("OBSERVE ok=%s ids=%s issues=%s",
                 ok, data["recommended_product_ids"] if data else None, issues)

    if not ok or data is None or not data["reply"]:
        log.warning("ADAPT  still invalid after %d attempt(s) -> catalog fallback",
                    meta["attempts"])
        meta.update(used_fallback=True, stage="fallback", issues=issues)
        result = _fallback(fallback_query)
        result["meta"] = meta
        return result

    meta.update(stage="done", issues=issues)
    log.info("DONE   attempts=%d reprompts=%d ids=%s",
             meta["attempts"], meta["reprompts"], data["recommended_product_ids"])
    data["meta"] = meta
    return data
