"""
Shared team agentic loop: Plan -> Act -> Observe -> Adapt (spec section 4.3),
extended for Release 1 with MCP and RAG validation modes alongside the
Release 0 AI-mode.

Modes:
    ai  -> Release 0 AI-mode: the local LLM answers with no external context
    mcp -> validates using the shared MCP server on localhost:6003
    rag -> validates using the shared RAG server on localhost:6002

Stages (local Ollama does Act and Observe):
    PLAN    gather evidence for the mode (MCP tool result, RAG answer, or none)
    ACT     answer the request (grounded only in the evidence for mcp/rag)
    OBSERVE check the answer: grounded in the evidence (mcp/rag) or
            well-formed and on-topic (ai)
    ADAPT   if OBSERVE rejects, turn its feedback into a correction and retry

PASS means OBSERVE accepted an answer within the retry budget. If PLAN gets
no evidence (MCP error, RAG insufficient context, server down) the loop fails
before ACT runs, so it never invents an answer.
"""

import importlib.util
import json
import os
from pathlib import Path

import requests

MCP_HOST = os.getenv("MCP_HOST", "http://localhost:6003")
RAG_HOST = os.getenv("RAG_HOST", "http://localhost:6002")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

if not OLLAMA_HOST.startswith("http"):
    OLLAMA_HOST = f"http://{OLLAMA_HOST}"
OLLAMA_HOST = OLLAMA_HOST.replace("0.0.0.0", "localhost")

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "1"))
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
RAG_TIMEOUT = int(os.getenv("RAG_TIMEOUT", "125"))

# MCP CLIENT LOADER
def _load_mcp_client():
    mcp_client_path = (
        Path(__file__).resolve().parent.parent
        / "mcp-server"
        / "client.py"
    )

    if not mcp_client_path.exists():
        raise FileNotFoundError(
            f"MCP client not found at {mcp_client_path}"
        )
    spec = importlib.util.spec_from_file_location(
        "mcp_client_local",
        mcp_client_path,
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Could not load MCP client from {mcp_client_path}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.McpClient, module.McpError

# OLLAMA
def ollama_json(prompt):
    """Ask local Ollama for one JSON object."""
    response = requests.post(
        f"{OLLAMA_HOST.rstrip('/')}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.0
            },
        },
        timeout=OLLAMA_TIMEOUT,
    )
    response.raise_for_status()
    raw = response.json().get("response", "")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")

        if start >= 0 and end > start:
            return json.loads(raw[start:end + 1])

        raise ValueError("Ollama did not return valid JSON")

# MCP VALIDATION
def mcp_validate(tool_name, tool_arguments=None):
    try:
        McpClient, McpError = _load_mcp_client()
        mcp = McpClient(MCP_HOST)
        info = mcp.initialize("shared-agentic-validator")
        result = mcp.call_tool(
            tool_name,
            tool_arguments or {},
        )
        if result.get("isError"):
            message = result.get(
                "content",
                [{}]
            )[0].get(
                "text",
                "MCP tool returned an error"
            )
            return {
                "available": False,
                "error": message,
            }
        
        return {
            "available": True,
            "server": info.get("serverInfo"),
            "protocolVersion": info.get("protocolVersion"),
            "tool": tool_name,
            "arguments": tool_arguments or {},
            "data": result.get("structuredContent"),
        }
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc),
        }

# RAG VALIDATION
def rag_validate(ticket):
    question = (
        ticket.get("question")
        or ticket.get("query")
        or ticket.get("description")
        or str(ticket)
    )
    try:
        response = requests.post(
            f"{RAG_HOST.rstrip('/')}/rag/query",
            json={"query": question},
            timeout=RAG_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("insufficient_context"):
            return {
                "available": False,
                "error": data.get(
                    "message",
                    "RAG returned insufficient context",
                ),
                "data": data,
            }
        return {
            "available": True,
            "data": data,
        }
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc),
        }

# PLAN (Release 0 AI-mode): no external evidence
def ai_mode_context(ticket):
    return {
        "available": True,
        "mode": "ai",
        "note": "Release 0 AI-mode: no external context; the local LLM answers directly.",
    }


# ACT
def act(ticket, evidence, correction="", grounded=True):
    if grounded:
        rules = (
            "Answer the request using ONLY the supplied validation evidence.\n"
            "Do not invent facts that are not present in the evidence.\n"
            "The reasoning must explain how the evidence supports the answer."
        )
    else:
        rules = (
            "Answer the request directly using your own knowledge (Release 0 AI-mode,\n"
            "no retrieved context). Do not claim to have used any sources.\n"
            "The reasoning must explain how you reached the answer."
        )
    prompt = f"""
You are the ACT step of a Plan -> Act -> Observe -> Adapt agentic loop.

{rules}

REQUEST:
{json.dumps(ticket, indent=2)}

VALIDATION EVIDENCE:
{json.dumps(evidence, indent=2)}

Correction from the previous OBSERVE step (empty on the first attempt):
{correction}

Return ONLY JSON in this format:

{{
  "answer": "your answer",
  "reasoning": "your reasoning"
}}
"""
    return ollama_json(prompt)


# OBSERVE
def observe(ticket, evaluation, evidence, grounded=True):
    if grounded:
        check = (
            "Check whether the ACT answer and reasoning are supported by the\n"
            "supplied validation evidence. Reject anything stated that is not in\n"
            "the evidence. Do NOT introduce outside knowledge."
        )
    else:
        check = (
            "This is Release 0 AI-mode, so there is no evidence to ground against.\n"
            "Check that the ACT answer actually addresses the request, that the\n"
            "reasoning supports the answer, and that it does not claim to cite sources."
        )
    prompt = f"""
You are the OBSERVE step of a Plan -> Act -> Observe -> Adapt agentic loop.
Do NOT answer the request yourself; only judge the ACT output.

{check}

REQUEST:
{json.dumps(ticket, indent=2)}

VALIDATION EVIDENCE:
{json.dumps(evidence, indent=2)}

ACT OUTPUT:
{json.dumps(evaluation, indent=2)}

If the ACT output passes, return:
{{
  "status": "APPROVED",
  "feedback": "Why the answer passes."
}}

If it does not, return:
{{
  "status": "REJECTED",
  "feedback": "Exactly what is unsupported, missing, or incorrect."
}}

Return ONLY JSON.
"""
    return ollama_json(prompt)


# ADAPT
def adapt(observation):
    return (
        "Your previous answer was rejected by the OBSERVE step: "
        + observation.get("feedback", "Correct the previous answer.")
        + " Produce a corrected answer that fixes this."
    )


def _ollama_failure(validation_mode, evidence, attempts, exc):
    """Evidence was retrieved but the local LLM failed - report it, don't crash."""
    print(f"\nOllama unavailable or returned invalid output: {exc}")
    return {
        "status": "FAIL",
        "validation_mode": validation_mode,
        "error": f"Ollama unavailable or returned invalid output: {exc}",
        "evidence": evidence,
        "attempts": attempts,
    }


_ACCEPTED = {"APPROVED", "PASS", "PASSED", "CORRECT", "VALID", "ACCEPTED"}


# SHARED AGENTIC LOOP
def run_agentic_evaluation(
    ticket,
    *,
    validation_mode,
    mcp_tool_name=None,
    mcp_arguments=None,
    max_retries=MAX_RETRIES,
):
    print("\n========================================")
    print("SHARED AGENTIC LOOP  (Plan -> Act -> Observe -> Adapt)")
    print("========================================")
    print(f"Validation mode: {validation_mode.upper()}")

    # PLAN
    print("\n[PLAN]")
    if validation_mode == "mcp":
        if not mcp_tool_name:
            raise ValueError("--tool is required when using MCP validation")
        evidence = mcp_validate(mcp_tool_name, mcp_arguments)
    elif validation_mode == "rag":
        evidence = rag_validate(ticket)
    elif validation_mode == "ai":
        evidence = ai_mode_context(ticket)
    else:
        raise ValueError("validation_mode must be 'ai', 'mcp' or 'rag'")
    print(json.dumps(evidence, indent=2))

    if not evidence["available"]:
        return {
            "status": "FAIL",
            "validation_mode": validation_mode,
            "error": evidence.get("error"),
            "evidence": evidence,
        }

    grounded = validation_mode != "ai"
    correction = ""
    attempts = []

    for attempt in range(1, max_retries + 2):
        # ACT
        print(f"\n[ACT] attempt {attempt}")
        try:
            evaluation = act(ticket, evidence, correction, grounded=grounded)
        except (requests.RequestException, ValueError) as exc:
            return _ollama_failure(validation_mode, evidence, attempts, exc)
        if not isinstance(evaluation, dict):
            evaluation = {}
        print("Answer   :", evaluation.get("answer"))
        print("Reasoning:", evaluation.get("reasoning"))

        # OBSERVE
        print(f"\n[OBSERVE] attempt {attempt}")
        if (
            not str(evaluation.get("answer", "")).strip()
            or not str(evaluation.get("reasoning", "")).strip()
        ):
            observation = {
                "status": "REJECTED",
                "feedback": "The AI did not return both required fields: answer and reasoning.",
            }
        else:
            try:
                observation = observe(ticket, evaluation, evidence, grounded=grounded)
            except (requests.RequestException, ValueError) as exc:
                return _ollama_failure(validation_mode, evidence, attempts, exc)
            if not isinstance(observation, dict):
                observation = {
                    "status": "REJECTED",
                    "feedback": "The OBSERVE step did not return a JSON object.",
                }
        print("Status   :", observation.get("status"))
        print("Feedback :", observation.get("feedback"))

        attempts.append({"attempt": attempt, "evaluation": evaluation, "observation": observation})

        if str(observation.get("status", "")).upper() in _ACCEPTED:
            return {
                "status": "PASS",
                "answer": evaluation.get("answer"),
                "reasoning": evaluation.get("reasoning"),
                "validation_mode": validation_mode,
                "evidence": evidence,
                "attempts": attempts,
            }

        # ADAPT
        if attempt <= max_retries:
            print(f"\n[ADAPT] attempt {attempt}")
            correction = adapt(observation)
            print(correction)

    final = attempts[-1]["evaluation"]
    return {
        "status": "FAIL",
        "answer": final.get("answer"),
        "reasoning": final.get("reasoning"),
        "validation_mode": validation_mode,
        "evidence": evidence,
        "attempts": attempts,
    }


def print_report(result):
    print("\n========================================")
    print("FINAL VALIDATION RESULT")
    print("========================================")
    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )