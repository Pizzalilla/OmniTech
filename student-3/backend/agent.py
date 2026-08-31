"""
Agentic consultation loop for the AI Product Consultant.

    Plan     Pull relevant catalog rows and build the context for the request.
    Act      Send a structured, contextual prompt to the local Ollama API.
    Observe   Validate the model output - is it well-formed JSON, and does it
              only recommend product ids that exist in the catalog?
    Adapt     On failure, send one corrective re-prompt with the exact problems
              and re-validate. If Ollama cannot be reached at all, fall back to a
              deterministic catalog keyword match so the feature still responds.

`run_consultation()` is the single entry point used by the Flask layer and never
raises - callers always receive a usable dict.
"""

import json
import os
import re

import requests

import catalog

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
MAX_REPROMPTS = 1

SYSTEM_INSTRUCTIONS = (
    "You are the OmniTech Marketplace AI Product Consultant for consumer "
    "electronics. Recommend the best products for the customer's stated needs, "
    "budget and preferences.\n"
    "Rules:\n"
    "1. Recommend ONLY products from the PRODUCT CATALOG below.\n"
    "2. Put the exact catalog id of every product you recommend in "
    "recommended_product_ids, and also mention it in reply.\n"
    "3. Never invent products, brands, models or ids. Never write the word "
    '"ID" literally - use real ids such as LAP-001 or AUD-002.\n'
    "4. Answer with ONE JSON object and nothing else. Keys: reply (string), "
    "recommended_product_ids (array of catalog id strings), summary (string).\n"
    "5. recommended_product_ids may be empty only when you ask a clarifying "
    "question - put that question in reply.\n"
    "\n"
    "Example of a good answer:\n"
    '{"reply": "For 4K editing the Meridian Pro 16 (LAP-001) is the pick - '
    '16-core CPU and 32GB RAM. If you also want portability, the Meridian Air '
    '13 (LAP-002) is lighter.", "recommended_product_ids": ["LAP-001", '
    '"LAP-002"], "summary": "A workstation laptop for heavy 4K timelines, with '
    'a lighter alternative."}'
)


# --------------------------------------------------------------------------- #
# Plan
# --------------------------------------------------------------------------- #
def plan(user_message, history):
    """Retrieve catalog context relevant to the request."""
    relevant = catalog.search(user_message)
    return {
        "relevant_products": relevant,
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
        'Answer with one JSON object: {"reply": "...", '
        '"recommended_product_ids": ["LAP-001"], "summary": "..."}  '
        "(use the real catalog ids that fit this customer)"
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


def observe(raw_text, valid_ids):
    """Validate a raw completion.

    Returns (ok, data, issues). `data` is a normalised dict (or None if the
    output was not JSON at all); `issues` lists the problems found.
    """
    issues = []
    data = _extract_json(raw_text)
    if data is None:
        return False, None, ["output was not valid JSON in the required shape"]

    reply = str(data.get("reply", "")).strip()
    summary = str(data.get("summary", "")).strip()
    ids = data.get("recommended_product_ids", [])
    if not isinstance(ids, list):
        issues.append("recommended_product_ids must be a list of id strings")
        ids = []
    ids = [str(i).strip() for i in ids]

    if not reply:
        issues.append("the 'reply' field is missing or empty")

    # The final recommendation set is the union of valid ids in the list and
    # valid catalog ids the model named in the reply text - mentioning an id in
    # prose counts as recommending it.
    listed = [i for i in ids if i in valid_ids]
    named = [i for i in sorted(valid_ids) if i in reply]
    final_ids = list(dict.fromkeys(listed + named))

    # A genuinely invented id is a hard error; the literal placeholder "ID"
    # from the prompt template is just ignored.
    invented = [i for i in ids if i not in valid_ids and i.upper() != "ID"]
    if invented:
        issues.append("these product ids are not in the catalog: " + ", ".join(invented))

    asks_question = "?" in reply
    if not final_ids and not asks_question:
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
def _fallback(user_message):
    picks = catalog.search(user_message, limit=3)[:2]
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
    plan_ctx = plan(user_message, history)
    valid_ids = set(plan_ctx["valid_ids"])
    meta = {
        "attempts": 0, "reprompts": 0, "used_fallback": False,
        "stage": "plan", "issues": [],
    }

    # Act
    try:
        meta["attempts"] += 1
        meta["stage"] = "act"
        raw = act(_build_prompt(plan_ctx, history, user_message))
    except requests.RequestException as exc:
        meta.update(used_fallback=True, stage="fallback",
                    issues=[f"ollama unreachable: {exc}"])
        result = _fallback(user_message)
        result["meta"] = meta
        return result

    # Observe
    meta["stage"] = "observe"
    ok, data, issues = observe(raw, valid_ids)

    # Adapt
    while not ok and meta["reprompts"] < MAX_REPROMPTS:
        meta["reprompts"] += 1
        meta["stage"] = "adapt"
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
        ok, data, issues = observe(raw, valid_ids)

    if not ok or data is None or not data["reply"]:
        meta.update(used_fallback=True, stage="fallback", issues=issues)
        result = _fallback(user_message)
        result["meta"] = meta
        return result

    meta.update(stage="done", issues=issues)
    data["meta"] = meta
    return data
