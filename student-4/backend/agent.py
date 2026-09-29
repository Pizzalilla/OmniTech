"""
Student 4 AI helper agent (Release 1): grounded cart advice.

PLAN    gather real facts: product specs from orders.db, safety checks worked
        out in Python, and store knowledge from the shared RAG server
ACT     ask the shared Ollama model to answer using ONLY those facts
OBSERVE check every number in the answer against the facts
ADAPT   retry once with feedback; if it still invents numbers, show the
        facts-only answer instead
"""

import os
import re
from itertools import combinations

import requests

import database as db


# OLLAMA ADDRESS: Windows often sets OLLAMA_HOST=0.0.0.0:11434 (a listen address),
# so add http:// and swap 0.0.0.0 for 127.0.0.1 to get an address we can call
def ollama_url(raw):
    url = (raw or "127.0.0.1:11434").strip().rstrip("/")
    if "://" not in url:
        url = "http://" + url
    return url.replace("://0.0.0.0", "://127.0.0.1")


OLLAMA_HOST = ollama_url(os.getenv("OLLAMA_HOST"))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "90"))
RAG_HOST = os.getenv("RAG_HOST", "http://127.0.0.1:6002")
RAG_TIMEOUT = int(os.getenv("RAG_TIMEOUT", "10"))
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() != "false"   # CI sets RAG_ENABLED=false

VOLTS = 240
SOCKET_10A_W = 2400   # 240V x 10A
HEAVY_ITEM_KG = 30
AUDIT_QUERY = "power point circuit 10A clearance ventilation delivery accessories"

# STANDARD NUMBERS: always allowed in an answer (AU mains + circuit sizes)
STANDARD_NUMBERS = {
    "V": {230, 240},
    "A": {10, 15, 20, 32},
    "W": {SOCKET_10A_W, 3600},
    "kg": {HEAVY_ITEM_KG},
}


# ---------------------------------------------------------------------------
# PLAN: collect facts
# ---------------------------------------------------------------------------

# FACTS: cart items joined with their specs from orders.db
def get_cart_facts(items):
    specs = db.get_product_specs(i["product_id"] for i in items)
    facts = []
    for item in items:
        spec = specs.get(item["product_id"], {})
        facts.append({**spec, **item, "has_specs": bool(spec)})
    return facts


# CHECKS: safety rules worked out in Python, not by the AI
def run_cart_checks(facts):
    checks = []
    heaters = [f for f in facts if (f.get("power_w") or 0) >= 1000]

    for f in facts:
        name = f["product_name"]
        if not f["has_specs"]:
            checks.append({"level": "warn", "text": f"{name}: no specs on file, so the AI can't check it."})
            continue
        plug = f.get("plug") or ""
        if "Hardwired" in plug:
            checks.append({"level": "warn", "text": f"{name}: {plug} - needs a licensed electrician to install."})
        if (f.get("weight_kg") or 0) > HEAVY_ITEM_KG:
            checks.append({"level": "info", "text": f"{name}: {f['weight_kg']:g} kg - two-person delivery, measure doorways first."})
        if not f.get("in_stock", True):
            checks.append({"level": "warn", "text": f"{name}: out of stock - goes on backorder."})

    plug_in = [f for f in heaters if "10A" in (f.get("plug") or "")]
    if len(plug_in) >= 2:
        total_w = sum(f["power_w"] for f in plug_in)
        names = " + ".join(f["product_name"] for f in plug_in)
        if total_w > SOCKET_10A_W:
            checks.append({
                "level": "warn",
                "text": f"{names} = {total_w:g}W ({total_w / VOLTS:.1f}A) together - more than one 10A power point "
                        f"({SOCKET_10A_W}W). Use separate power points, no double adaptors.",
            })

    if not checks:
        checks.append({"level": "ok", "text": "No power, delivery or stock problems found."})
    return checks


# RAG: store knowledge from the shared RAG server
# returns (chunks, status, confidence); status = ok / insufficient / offline / disabled
def retrieve_knowledge(query, limit=3):
    if not RAG_ENABLED:
        return [], "disabled", None
    try:
        resp = requests.post(f"{RAG_HOST}/rag/retrieve", json={"query": query, "limit": limit}, timeout=RAG_TIMEOUT)
        if resp.status_code == 404:
            # OLDER RAG SERVER: no /rag/retrieve yet, use citations from /rag/query
            resp = requests.post(f"{RAG_HOST}/rag/query", json={"query": query}, timeout=RAG_TIMEOUT * 12)
            body = resp.json()
            chunks = [{"source": c["source"], "heading": c["section"], "text": c["snippet"]}
                      for c in body.get("citations", [])][:limit]
        else:
            resp.raise_for_status()
            body = resp.json()
            chunks = body.get("chunks", [])[:limit]
        if not chunks:
            return [], "insufficient", None
        return chunks, "ok", body.get("confidence")
    except (requests.RequestException, ValueError, KeyError):
        return [], "offline", None


# FACT SHEET: turn facts into plain lines for the prompt (and the fallback answer)
def describe_product(f):
    if not f["has_specs"]:
        return f"{f['quantity']}x {f['product_name']}: no specs on file."
    parts = [f"{f['quantity']}x {f['product_name']}"]
    if f.get("power_w"):
        parts.append(f"{f['power_w']:g}W max draw ({f['power_w'] / VOLTS:.1f}A at {VOLTS}V), {f['plug']}")
    else:
        parts.append(f"{f.get('plug') or 'no power'}")
    parts.append(f"{f['width_mm']}mm W x {f['height_mm']}mm H x {f['depth_mm']}mm D, {f['weight_kg']:g} kg")
    if f.get("capacity_l"):
        parts.append(f"{f['capacity_l']:g} L")
    clear = [(k, f.get(f"{k}_clear_mm")) for k in ("rear", "side", "top")]
    clear = [f"{k} {v}mm" for k, v in clear if v]
    if clear:
        parts.append("clearance " + ", ".join(clear))
    if f.get("energy_stars"):
        parts.append(f"{f['energy_stars']:g}-star energy rating, {f['kwh_per_year']:g} kWh/year")
    if f.get("accessory"):
        parts.append(f"suggested accessory: {f['accessory']}")
    parts.append("in stock" if f.get("in_stock", True) else "out of stock")
    return "; ".join(parts) + "."


# ---------------------------------------------------------------------------
# ACT: ask the LLM
# ---------------------------------------------------------------------------

# PROMPT: facts first, then the task
def build_prompt(question, facts, checks, knowledge, feedback=None):
    lines = ["PRODUCT FACTS (from the OmniTech database):"]
    lines += [f"- {describe_product(f)}" for f in facts] or ["- The cart is empty."]
    lines += ["", "SAFETY CHECKS (already calculated):"]
    lines += [f"- {c['text']}" for c in checks]
    if knowledge:
        lines += ["", "STORE KNOWLEDGE:"]
        lines += [f"[{i}] {k['heading']}: {k['text']}" for i, k in enumerate(knowledge, 1)]
    lines.append("")
    if question:
        lines.append(f"CUSTOMER QUESTION: {question}")
        lines.append("Answer in at most 3 short sentences.")
    else:
        lines.append("TASK: Audit this cart in 2 short bullet points: 1) power / power points, 2) space, clearance and delivery. "
                     "Mention one suggested accessory if there is one.")
    if feedback:
        lines.append(f"Your last answer used numbers that are NOT in the facts: {feedback}. "
                     "Rewrite it using only numbers from the facts above.")
    return "\n".join(lines)


SYSTEM_PROMPT = (
    "You are the OmniTech Australia cart assistant. Use ONLY the facts you are given - never guess or add "
    "numbers that are not in the facts. If the facts do not answer the question, say you don't have that "
    "information. Use metric units (mm, cm, kg, L, W, A, kWh/year)."
)


# LLM CALL: Ollama chat API (raises requests.RequestException if Ollama is down)
def ask_llm(prompt):
    resp = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 300},
        },
        timeout=OLLAMA_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


# ---------------------------------------------------------------------------
# OBSERVE: check the numbers
# ---------------------------------------------------------------------------

NUMBER_WITH_UNIT = re.compile(
    r"(\d+(?:\.\d+)?)\s*-?\s*(kwh|kw|w|a|v|mm|cm|m|kg|l|stars?|litres?|liters?|watts?|amps?)(?![a-z])",
    re.IGNORECASE,
)
UNIT_FAMILY = {
    "kwh": ("kWh", 1), "kw": ("W", 1000), "w": ("W", 1), "watt": ("W", 1), "watts": ("W", 1),
    "a": ("A", 1), "amp": ("A", 1), "amps": ("A", 1), "v": ("V", 1),
    "mm": ("mm", 1), "cm": ("mm", 10), "m": ("mm", 1000), "kg": ("kg", 1),
    "l": ("L", 1), "litre": ("L", 1), "litres": ("L", 1), "liter": ("L", 1), "liters": ("L", 1),
    "star": ("stars", 1), "stars": ("stars", 1),
}


# NUMBERS: pull (value, unit family) pairs out of any text
def extract_numbers(text):
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text or "")
    found = []
    for match in NUMBER_WITH_UNIT.finditer(text):
        value, unit = match.groups()
        family, scale = UNIT_FAMILY[unit.lower()]
        found.append((float(value) * scale, family, match.group(0)))
    return found


# ALLOWED NUMBERS: everything the answer is allowed to say
def allowed_numbers(fact_text, question="", powers=()):
    allowed = {family: set(values) for family, values in STANDARD_NUMBERS.items()}
    for value, family, _ in extract_numbers(fact_text + " " + question):
        allowed.setdefault(family, set()).add(value)

    # TOTALS: the AI may add appliance wattages together, so allow every sum
    powers = [p for p in powers if p]
    for size in range(2, len(powers) + 1):
        for combo in combinations(powers, size):
            allowed["W"].add(sum(combo))
            allowed["A"].add(round(sum(combo) / VOLTS, 1))
    return allowed


# VERIFY: return the numbers in the answer that are not backed by facts
def find_unsupported(answer, allowed):
    unsupported = []
    for value, family, label in extract_numbers(answer):
        ok = any(abs(value - a) <= max(0.05 * a, 0.1) for a in allowed.get(family, ()))
        if not ok:
            unsupported.append(label)
    return unsupported


# ---------------------------------------------------------------------------
# ADAPT + RUN: the whole Plan -> Act -> Observe -> Adapt loop
# ---------------------------------------------------------------------------

# FALLBACK: facts-only answer when the AI can't be trusted or is offline
def facts_only_answer(facts, checks):
    lines = [describe_product(f) for f in facts] or ["The cart is empty."]
    return "\n".join(lines + [c["text"] for c in checks if c["level"] != "ok"])


def run_cart_agent(question, items):
    trace = []

    # PLAN
    facts = get_cart_facts(items)
    checks = run_cart_checks(facts)
    names = " ".join(f["product_name"] for f in facts)
    knowledge, rag_status, rag_confidence = retrieve_knowledge(question or f"{AUDIT_QUERY} {names}")
    rag_note = {"ok": f"confidence {rag_confidence}", "insufficient": "not enough information in the store knowledge",
                "offline": "RAG server offline", "disabled": "RAG disabled"}[rag_status]
    trace.append(f"Plan: loaded specs for {sum(f['has_specs'] for f in facts)}/{len(facts)} cart items, "
                 f"ran {len(checks)} safety checks, RAG returned {len(knowledge)} knowledge section(s) ({rag_note}).")

    fact_text = "\n".join(describe_product(f) for f in facts) + "\n" + "\n".join(c["text"] for c in checks)
    fact_text += "\n" + "\n".join(k["text"] for k in knowledge)
    allowed = allowed_numbers(fact_text, question, [f.get("power_w") for f in facts])

    result = {
        "question": question, "checks": checks, "knowledge": knowledge, "rag_status": rag_status,
        "rag_confidence": rag_confidence,
        "facts_used": sum(f["has_specs"] for f in facts), "trace": trace,
    }

    feedback = None
    for attempt in (1, 2):
        # ACT
        try:
            answer = ask_llm(build_prompt(question, facts, checks, knowledge, feedback))
        except (requests.RequestException, KeyError, ValueError) as exc:
            trace.append(f"Act: Ollama unreachable ({type(exc).__name__}).")
            trace.append("Adapt: showing the facts-only answer instead.")
            return {**result, "status": "offline", "answer": facts_only_answer(facts, checks)}
        trace.append(f"Act: attempt {attempt} - asked {OLLAMA_MODEL} to answer from the facts.")

        # OBSERVE
        unsupported = find_unsupported(answer, allowed)
        if not unsupported:
            trace.append(f"Observe: all {len(extract_numbers(answer))} number(s) in the answer match the facts.")
            return {**result, "status": "verified", "answer": answer, "attempts": attempt}
        trace.append(f"Observe: unsupported number(s) {', '.join(unsupported)}.")

        # ADAPT
        feedback = ", ".join(unsupported)
        if attempt == 1:
            trace.append("Adapt: retrying once with feedback.")

    trace.append("Adapt: still unsupported after retry - showing the facts-only answer.")
    return {**result, "status": "fallback", "answer": facts_only_answer(facts, checks),
            "rejected_answer": answer, "unsupported": unsupported, "attempts": 2}
