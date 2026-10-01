"""
Shared agentic loop validator for MCP and RAG.

Modes:
    MCP -> validates using the shared MCP server on localhost:6003
    RAG -> validates using the shared RAG server on localhost:6002

The loop itself uses local Ollama for:
    PLAN -> ACT -> REVIEW

ACT generates an answer and reasoning based only on the retrieved evidence.
REVIEW checks whether the answer and reasoning are supported by that evidence.
Validation PASS means the reviewer agrees that the output is evidence-grounded.
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

# ACT
def act(ticket, evidence, correction=""):
    prompt = f"""
You are the ACT agent in a shared agentic-loop validation test.

Your job is to answer the user's request using ONLY the supplied validation
evidence.

TICKET:
{json.dumps(ticket, indent=2)}

VALIDATION EVIDENCE:
{json.dumps(evidence, indent=2)}

Previous reviewer correction:
{correction}

Generate an answer that is directly supported by the evidence.

Do not invent facts that are not present in the evidence.

Return ONLY JSON in this format:

{{
  "answer": "your answer based on the evidence",
  "reasoning": "explain how the evidence supports the answer"
}}

The answer must address the request in the ticket.
The reasoning must explain the connection between the evidence and the answer.
"""
    
    return ollama_json(prompt)

# REVIEW
def review(ticket, evaluation, evidence):
    prompt = f"""
You are the REVIEW agent in a shared agentic-loop validation test.

Your job is to check whether the ACT agent's answer and reasoning are
supported by the supplied validation evidence.

Do NOT answer the ticket yourself.
Do NOT introduce outside knowledge.
Only judge whether the ACT output is grounded in the supplied evidence.

TICKET:
{json.dumps(ticket, indent=2)}

VALIDATION EVIDENCE:
{json.dumps(evidence, indent=2)}

ACT AGENT OUTPUT:
{json.dumps(evaluation, indent=2)}

If the answer and reasoning are supported by the evidence, return:

{{
  "status": "APPROVED",
  "feedback": "The answer and reasoning are supported by the evidence."
}}

If they are not sufficiently supported, return:

{{
  "status": "REJECTED",
  "feedback": "Explain exactly what information is unsupported, missing, or incorrect."
}}

Return ONLY JSON.
"""

    return ollama_json(prompt)


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
    print("SHARED AGENTIC LOOP")
    print("========================================")
    print(f"Validation mode: {validation_mode.upper()}")

    # PLAN
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

    # ACT → REVIEW
    for attempt in range(1, max_retries + 2):
        print(f"\n[ATTEMPT {attempt}]")
        evaluation = act(
            ticket,
            evidence,
            correction,
        )
        print("AI answer   :", evaluation.get("answer"))
        print("AI reasoning:", evaluation.get("reasoning"))
        if (
            not isinstance(evaluation, dict)
            or "answer" not in evaluation
            or "reasoning" not in evaluation
            or not str(evaluation["answer"]).strip()
            or not str(evaluation["reasoning"]).strip()
        ):
            review_result = {
                "status": "REJECTED",
                "feedback": (
                    "The AI did not return both required fields: "
                    "answer and reasoning."
                ),
            }
        else:
            review_result = review(
                ticket,
                evaluation,
                evidence,
            )
        print("Review      :", review_result.get("status"),)
        print("Feedback    :", review_result.get("feedback"),)
        attempts.append({
            "attempt": attempt,
            "evaluation": evaluation,
            "review": review_result,
        })
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
                "answer": evaluation.get("answer"),
                "reasoning": evaluation.get("reasoning"),
                "validation_mode": validation_mode,
                "evidence": evidence,
                "attempts": attempts,
            }
        correction = review_result.get(
            "feedback",
            "Correct the previous answer.",
        )

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