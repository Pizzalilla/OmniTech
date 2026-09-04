"""
Agentic Workflow for Customer Profiles & Preferences:
Plan   -> Retrieve user profile context and preferences.
Act    -> Prompt local Ollama for candidate ecosystem preference tags.
Observe -> Validate candidate tags against system categories.
Adapt  -> Retries on invalid output, falls back to deterministic rule mapping if Ollama is down.
"""
import json
import logging
import os
import re
import requests
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "database"))
from database import SYSTEM_CATEGORIES

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))


logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO
)

log = logging.getLogger("users.agent")
log.setLevel(logging.INFO)

SYSTEM_PROMPT = f"""
You are an AI Profile Preference Agent for OmniTech Marketplace.
Analyze the user's profile, preferences, and notes to pick valid ecosystem preference tags.

Allowed system categories:
{', '.join(sorted(SYSTEM_CATEGORIES))}

Rules:
1. Output ONLY a valid JSON object.
2. JSON keys:
   - "recommended_tags": Array of tag strings chosen strictly from the allowed list above.
   - "reasoning": Short explanation string.
"""

def plan(customer, preferences):
    pref_summary = [f"Ecosystem: {p['ecosystem']}, Budget: {p['budget_tier']}, Notes: {p['notes']}" for p in preferences]
    plan_data = {
        "customer_id": customer["id"],
        "name": f"{customer['first_name']} {customer['last_name']}",
        "preferences_text": " | ".join(pref_summary) or "No specified preferences."
    }

    log.info(f"PLAN Context retrieved for Customer #{plan_data['customer_id']} ({plan_data['name']})")
    log.info(f"PLAN Preferences Summary: {plan_data['preferences_text']}")
    return plan_data

def act(prompt):
    log.info(f"ACT Prompting Ollama ({OLLAMA_MODEL}) at {OLLAMA_HOST}...")

    resp = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0},
        },
        timeout=OLLAMA_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("response", "")

def observe(raw_text):
    log.info(f"OBSERVE Inspecting output payload against allowed system categories")
    if not raw_text:
        return False, None, ["empty completion response"]
    
    cleaned_raw = re.sub(r"```json\s*", "", raw_text, flags=re.IGNORECASE)
    cleaned_raw = re.sub(r"```\s*", "", cleaned_raw).strip()

    data = None
    try:
        data = json.loads(cleaned_raw)
    except Exception:
        match = re.search(r"\{.*\}", cleaned_raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                return False, None, ["output not valid JSON"]
        else:
            return False, None, ["output not valid JSON"]

    tags = data.get("recommended_tags", [])
    if not isinstance(tags, list):
        return False, None, ["recommended_tags must be a list"]

    cleaned_tags = []
    issues = []
    for t in tags:
        normalized = str(t).strip().lower().replace(" ", "-")
        if normalized in SYSTEM_CATEGORIES:
            if normalized not in cleaned_tags:
                cleaned_tags.append(normalized)
        else:
            issues.append(f"tag '{t}' is not in allowed system categories")

    reasoning = str(data.get("reasoning", "")).strip() or "Generated from profile data."
    
    if cleaned_tags:
        log.info(f"OBSERVE Validation Passed Validated Tags: {cleaned_tags}")
        return True, {"recommended_tags": cleaned_tags, "reasoning": reasoning}, []
    
    return False, None, issues or ["No valid system categories found"]


def fallback_plan(plan_ctx):
    log.info("ADAPT Triggering deterministic rule-based fallback pathway")

    text = plan_ctx["preferences_text"].lower()
    found = set()
    if "apple" in text: found.add("apple-ecosystem")
    if "android" in text: found.add("android-ecosystem")
    if "windows" in text: found.add("windows-ecosystem")
    if "gaming" in text: found.add("pc-gaming")
    if "4k" in text or "editing" in text: found.add("4k-video-editing")
    if "smart" in text or "home" in text: found.add("smart-home-enthusiast")
    if "budget" in text: found.add("budget-conscious")
    if "premium" in text: found.add("premium-tech")

    if not found:
        found.add("budget-conscious")

    res = {
        "recommended_tags": list(found),
        "reasoning": "Offline rule-based tag extraction based on preference keywords.",
        "meta": {"used_fallback": True}
    }

    log.info(f"ADAPT Fallback Done Extracted Tags: {res['recommended_tags']}")
    return res

def generate_user_tags(customer, preferences):
    plan_ctx = plan(customer, preferences)
    prompt = f"{SYSTEM_PROMPT}\n\nCustomer Profile Context:\nName: {plan_ctx['name']}\nPreferences: {plan_ctx['preferences_text']}\n"

    try:
        raw = act(prompt)
        ok, data, issues = observe(raw)
        if ok and data:
            data["meta"] = {"used_fallback": False, "issues": []}
            return data
        
        retry_prompt = f"{prompt}\nYour previous answer had issues: {'; '.join(issues)}. Return strictly a JSON object with allowed system tags."
        raw_retry = act(retry_prompt)
        ok_retry, data_retry, issues_retry = observe(raw_retry)
        if ok_retry and data_retry:
            data_retry["meta"] = {"used_fallback": False, "issues": issues_retry}
            return data_retry

    except Exception as e:
        log.warning("Ollama call failed: %s. Using fallback.", e)

    return fallback_plan(plan_ctx)