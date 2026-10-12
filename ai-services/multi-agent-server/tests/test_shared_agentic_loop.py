import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import shared_agentic_loop as loop  # noqa: E402


def _up(url):
    try:
        return requests.get(url, timeout=2).status_code < 500
    except requests.RequestException:
        return False


# Live tests need the local servers; they skip (not fail) when those aren't running.
requires_mcp = pytest.mark.skipif(
    not _up(f"{loop.MCP_HOST}/health"), reason="shared MCP server not running"
)
requires_rag_and_ollama = pytest.mark.skipif(
    not (_up(f"{loop.RAG_HOST}/health") and _up(f"{loop.OLLAMA_HOST}/api/tags")),
    reason="shared RAG server and/or Ollama not running",
)

# ============================================================
# FAKE TEST DATA
# ============================================================
#
# These records exist ONLY for testing the shared agentic loop.
# They are not used by the real MCP server or RAG server.
# ============================================================

FAKE_RAG_EVIDENCE = {
    "answer": (
        "Items can be returned within 30 days of delivery for a full refund, "
        "provided they are unused and in their original packaging."
    ),
    "citations": [
        {
            "section": "Return Window",
            "snippet": (
                "Items can be returned within 30 days of delivery for a full "
                "refund, provided they are unused and in their original packaging."
            ),
            "source": "shipping-and-returns.md",
        }
    ],
    "confidence": "high",
}


# ============================================================
# MCP TESTS
# ============================================================

@requires_mcp
def test_mcp_rejected_request_fails():
    # order_id 0 breaks the tool's input schema (minimum 1), so the shared MCP
    # server itself rejects it - no student service needs to be running.
    result = loop.run_agentic_evaluation(
        {
            "question": "What is the status of order 0?"
        },
        validation_mode="mcp",
        mcp_tool_name="get_order_status",
        mcp_arguments={
            "order_id": 0,
        },
    )

    assert result["status"] == "FAIL"
    assert result["validation_mode"] == "mcp"
    assert "at least 1" in result["error"]


# ============================================================
# RAG TESTS
# ============================================================

@requires_rag_and_ollama
def test_rag_return_policy_validation():
    result = loop.run_agentic_evaluation(
        {
            "question": "What is your return policy?"
        },
        validation_mode="rag",
    )

    assert result["status"] == "PASS"
    assert result["validation_mode"] == "rag"
    assert result["evidence"]["available"] is True

    evidence = result["evidence"]["data"]

    assert "citations" in evidence
    assert len(evidence["citations"]) > 0

# ============================================================
# REVIEW REJECTION / RETRY
# ============================================================

def test_review_rejection_causes_retry(monkeypatch):
    """
    Test that the shared loop retries when the reviewer rejects
    the first answer.
    """

    fake_evidence = {
        "available": True,
        "data": FAKE_RAG_EVIDENCE,
    }

    attempts = []

    def fake_rag_validate(ticket):
        return fake_evidence

    def fake_act(ticket, evidence, correction="", grounded=True):
        attempts.append(correction)

        if not correction:
            return {
                "answer": "The return policy is 60 days.",
                "reasoning": "The policy allows returns.",
            }

        return {
            "answer": (
                "Items can be returned within 30 days of delivery "
                "for a full refund if they are unused and in their "
                "original packaging."
            ),
            "reasoning": (
                "The retrieved evidence explicitly states a 30-day "
                "return period and the required conditions."
            ),
        }

    review_count = 0

    def fake_review(ticket, evaluation, evidence, grounded=True):
        nonlocal review_count
        review_count += 1

        if review_count == 1:
            return {
                "status": "REJECTED",
                "feedback": (
                    "The evidence states 30 days, not 60 days. "
                    "Correct the return period."
                ),
            }

        return {
            "status": "APPROVED",
            "feedback": (
                "The corrected answer is supported by the evidence."
            ),
        }

    monkeypatch.setattr(loop, "rag_validate", fake_rag_validate)
    monkeypatch.setattr(loop, "act", fake_act)
    monkeypatch.setattr(loop, "observe", fake_review)

    result = loop.run_agentic_evaluation(
        {
            "question": "What is your return policy?"
        },
        validation_mode="rag",
        max_retries=1,
    )

    assert result["status"] == "PASS"
    assert len(result["attempts"]) == 2

    assert result["attempts"][0]["observation"]["status"] == "REJECTED"
    assert result["attempts"][1]["observation"]["status"] == "APPROVED"

    # Make sure the reviewer's correction reached ACT.
    assert len(attempts) == 2
    assert attempts[0] == ""
    assert "30 days" in attempts[1]


# ============================================================
# EVIDENCE UNAVAILABLE
# ============================================================

def test_mcp_unavailable_fails_before_act(monkeypatch):
    """
    If MCP cannot provide evidence, the shared loop should fail
    during PLAN rather than asking ACT to invent an answer.
    """

    act_called = False

    def fake_mcp_validate(tool_name, tool_arguments=None):
        return {
            "available": False,
            "error": "Order 9999 not found",
        }

    def fake_act(ticket, evidence, correction="", grounded=True):
        nonlocal act_called
        act_called = True

        return {
            "answer": "This should never be generated.",
            "reasoning": "This should never be generated.",
        }

    monkeypatch.setattr(loop, "mcp_validate", fake_mcp_validate)
    monkeypatch.setattr(loop, "act", fake_act)

    result = loop.run_agentic_evaluation(
        {
            "question": "What is the status of order 9999?"
        },
        validation_mode="mcp",
        mcp_tool_name="get_order_status",
        mcp_arguments={"order_id": 9999},
    )

    assert result["status"] == "FAIL"
    assert result["validation_mode"] == "mcp"
    assert result["error"] == "Order 9999 not found"

    # ACT must not run when there is no evidence.
    assert act_called is False


# ============================================================
# INVALID ACT OUTPUT
# ============================================================

def test_invalid_act_output_is_rejected(monkeypatch):
    """
    Test that the reviewer rejects an ACT response that does not
    contain both answer and reasoning.
    """

    fake_evidence = {
        "available": True,
        "data": FAKE_RAG_EVIDENCE,
    }

    def fake_rag_validate(ticket):
        return fake_evidence

    def fake_act(ticket, evidence, correction="", grounded=True):
        return {
            "answer": "Some answer",
        }

    def fake_review(ticket, evaluation, evidence, grounded=True):
        raise AssertionError(
            "Review should not be called for invalid ACT output."
        )

    monkeypatch.setattr(loop, "rag_validate", fake_rag_validate)
    monkeypatch.setattr(loop, "act", fake_act)
    monkeypatch.setattr(loop, "observe", fake_review)

    result = loop.run_agentic_evaluation(
        {
            "question": "What is your return policy?"
        },
        validation_mode="rag",
        max_retries=0,
    )

    assert result["status"] == "FAIL"
    assert len(result["attempts"]) == 1

    assert (
        result["attempts"][0]["observation"]["status"]
        == "REJECTED"
    )

    assert (
        "required fields"
        in result["attempts"][0]["observation"]["feedback"]
    )

# ============================================================
# OLLAMA UNAVAILABLE
# ============================================================

def test_ollama_down_fails_cleanly_instead_of_crashing(monkeypatch):
    """Evidence was retrieved but the local LLM is unreachable: the loop
    must return a FAIL result, not raise a traceback."""

    def fake_rag_validate(ticket):
        return {"available": True, "data": FAKE_RAG_EVIDENCE}

    def fake_act(ticket, evidence, correction="", grounded=True):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(loop, "rag_validate", fake_rag_validate)
    monkeypatch.setattr(loop, "act", fake_act)

    result = loop.run_agentic_evaluation(
        {"question": "What is your return policy?"},
        validation_mode="rag",
    )

    assert result["status"] == "FAIL"
    assert "Ollama unavailable" in result["error"]
    assert result["evidence"]["available"] is True


def test_non_object_act_output_is_rejected(monkeypatch):
    """Ollama's JSON mode can return a list or string; that must be treated
    as an invalid answer, not crash on .get()."""

    monkeypatch.setattr(loop, "rag_validate",
                        lambda ticket: {"available": True, "data": FAKE_RAG_EVIDENCE})
    monkeypatch.setattr(loop, "act", lambda ticket, evidence, correction="", grounded=True: ["not", "a", "dict"])

    result = loop.run_agentic_evaluation(
        {"question": "What is your return policy?"},
        validation_mode="rag",
        max_retries=0,
    )

    assert result["status"] == "FAIL"
    assert "required fields" in result["attempts"][0]["observation"]["feedback"]


# ============================================================
# RELEASE 0 AI-MODE + ADAPT
# ============================================================

def test_ai_mode_runs_without_mcp_or_rag(monkeypatch):
    """Release 0 AI-mode needs no MCP/RAG; ACT and OBSERVE run ungrounded."""
    seen = {}

    def boom(*a, **k):
        raise AssertionError("ai mode must not call MCP or RAG")

    def fake_act(ticket, evidence, correction="", grounded=True):
        seen["act_grounded"] = grounded
        return {"answer": "Paris.", "reasoning": "It is the capital of France."}

    def fake_observe(ticket, evaluation, evidence, grounded=True):
        seen["observe_grounded"] = grounded
        return {"status": "APPROVED", "feedback": "Addresses the request."}

    monkeypatch.setattr(loop, "mcp_validate", boom)
    monkeypatch.setattr(loop, "rag_validate", boom)
    monkeypatch.setattr(loop, "act", fake_act)
    monkeypatch.setattr(loop, "observe", fake_observe)

    result = loop.run_agentic_evaluation(
        {"question": "What is the capital of France?"},
        validation_mode="ai",
    )

    assert result["status"] == "PASS"
    assert result["evidence"]["mode"] == "ai"
    assert seen == {"act_grounded": False, "observe_grounded": False}


def test_adapt_turns_observe_feedback_into_correction():
    correction = loop.adapt({"status": "REJECTED", "feedback": "Say 30 days, not 60."})
    assert "Say 30 days, not 60." in correction
    assert "OBSERVE" in correction
