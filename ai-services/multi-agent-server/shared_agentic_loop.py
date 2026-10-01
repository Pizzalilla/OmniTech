"""
Standalone shared agentic-loop validator for MCP and RAG.

This is independent of any student's Release-0 agent.

Modes:
    MCP -> validates using the shared MCP server on localhost:6003
    RAG -> validates using the shared RAG server on localhost:6002

The loop itself uses local Ollama for:
    PLAN -> ACT -> REVIEW

A business decision of REJECTED is still a valid decision.
Validation PASS means the reviewer agrees with the decision/reasoning.
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

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "1"))
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
RAG_TIMEOUT = int(os.getenv("RAG_TIMEOUT", "125"))


# ============================================================
# MCP CLIENT LOADER
# ============================================================

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


# ============================================================
# OLLAMA
# ============================================================

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


# ============================================================
# MCP VALIDATION
# ============================================================

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


# ============================================================
# RAG VALIDATION
# ============================================================

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


# ============================================================
# ACT
# ============================================================

def act(ticket, evidence, correction=""):
    prompt = f"""
You are the ACT agent in a shared agentic-loop validation test.

You are evaluating this marketplace/warranty case.

TICKET:
{json.dumps(ticket, indent=2)}

VALIDATION EVIDENCE:
{json.dumps(evidence, indent=2)}

Previous reviewer correction:
{correction}

Use the supplied evidence to make a business decision.

Return ONLY JSON:

{{
  "decision": "APPROVED" or "REJECTED",
  "reasoning": "explain why the decision follows from the evidence"
}}

A REJECTED decision is completely valid.
Do not treat REJECTED as an error.
"""

    return ollama_json(prompt)


# ============================================================
# REVIEW
# ============================================================

def review(ticket, evaluation, evidence):
    prompt = f"""
You are the REVIEW agent in a shared agentic-loop validation test.

Your job is NOT to decide whether the customer's claim should be approved
based on your own opinion.

Your job is to check whether the ACT agent's decision and reasoning are
supported by the supplied validation evidence.

TICKET:
{json.dumps(ticket, indent=2)}

VALIDATION EVIDENCE:
{json.dumps(evidence, indent=2)}

ACT AGENT OUTPUT:
{json.dumps(evaluation, indent=2)}

If the ACT decision and reasoning correctly follow the evidence, return:

{{
  "status": "APPROVED",
  "feedback": "The decision and reasoning are supported by the evidence."
}}

If they do not, return:

{{
  "status": "REJECTED",
  "feedback": "Explain exactly what needs to be corrected."
}}

IMPORTANT:
A business decision of REJECTED can still receive a reviewer status of
APPROVED. The two fields represent different things.

Return ONLY JSON.
"""

    return ollama_json(prompt)


# ============================================================
# SHARED AGENTIC LOOP
# ============================================================

def run_agentic_evaluation(
    ticket,
    *,
    validation_mode,
    mcp_tool_name=None,
    mcp_arguments=None,
    max_retries=MAX_RETRIES,
):
    print("\n========================================")
    print("SHARED AGENTIC LOOP")
    print("========================================")
    print(f"Validation mode: {validation_mode.upper()}")

    # --------------------------------------------------------
    # PLAN
    # --------------------------------------------------------

    print("\n[PLAN]")

    if validation_mode == "mcp":

        if not mcp_tool_name:
            raise ValueError(
                "--tool is required when using MCP validation"
            )

        evidence = mcp_validate(
            mcp_tool_name,
            mcp_arguments,
        )

    elif validation_mode == "rag":

        evidence = rag_validate(ticket)

    else:
        raise ValueError(
            "validation_mode must be 'mcp' or 'rag'"
        )

    print(
        json.dumps(
            evidence,
            indent=2,
        )
    )

    if not evidence["available"]:
        return {
            "status": "FAIL",
            "validation_mode": validation_mode,
            "error": evidence.get("error"),
        }

    correction = ""
    attempts = []

    # --------------------------------------------------------
    # ACT → REVIEW
    # --------------------------------------------------------

    for attempt in range(1, max_retries + 2):

        print(f"\n[ATTEMPT {attempt}]")

        evaluation = act(
            ticket,
            evidence,
            correction,
        )

        print("AI decision :", evaluation.get("decision"))
        print("AI reasoning:", evaluation.get("reasoning"))

        # Make sure the AI actually returned both fields.
        if (
            not isinstance(evaluation, dict)
            or "decision" not in evaluation
            or "reasoning" not in evaluation
            or not str(evaluation["reasoning"]).strip()
        ):

            review_result = {
                "status": "REJECTED",
                "feedback": (
                    "The AI did not return both required fields."
                ),
            }

        else:

            review_result = review(
                ticket,
                evaluation,
                evidence,
            )

        print(
            "Review      :",
            review_result.get("status"),
        )

        print(
            "Feedback    :",
            review_result.get("feedback"),
        )

        attempts.append({
            "attempt": attempt,
            "evaluation": evaluation,
            "review": review_result,
        })

        # ----------------------------------------------------
        # IMPORTANT:
        # REVIEW APPROVED = VALIDATION PASSED
        #
        # It does NOT matter whether:
        #
        # decision = APPROVED
        #
        # or:
        #
        # decision = REJECTED
        # ----------------------------------------------------

        if str(
            review_result.get("status", "")
        ).upper() in {
            "APPROVED",
            "PASS",
            "PASSED",
            "CORRECT",
            "VALID",
            "ACCEPTED",
        }:

            return {
                "status": "PASS",
                "decision": evaluation.get("decision"),
                "reasoning": evaluation.get("reasoning"),
                "validation_mode": validation_mode,
                "evidence": evidence,
                "attempts": attempts,
            }

        correction = review_result.get(
            "feedback",
            "Correct the previous answer.",
        )

    # --------------------------------------------------------
    # RETRIES EXHAUSTED
    # --------------------------------------------------------

    final = attempts[-1]["evaluation"]

    return {
        "status": "FAIL",
        "decision": final.get("decision"),
        "reasoning": final.get("reasoning"),
        "validation_mode": validation_mode,
        "evidence": evidence,
        "attempts": attempts,
    }


# ============================================================
# REPORT
# ============================================================

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