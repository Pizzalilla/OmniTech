import shared_agentic_loop as loop

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

def test_mcp_missing_order_fails():
    result = loop.run_agentic_evaluation(
        {
            "question": "What is the status of order 5?"
        },
        validation_mode="mcp",
        mcp_tool_name="get_order_status",
        mcp_arguments={
            "order_id": 5,
        },
    )

    assert result["status"] == "FAIL"
    assert result["validation_mode"] == "mcp"
    assert "not found" in result["error"].lower()


# ============================================================
# RAG TESTS
# ============================================================

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

    def fake_act(ticket, evidence, correction=""):
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

    def fake_review(ticket, evaluation, evidence):
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
    monkeypatch.setattr(loop, "review", fake_review)

    result = loop.run_agentic_evaluation(
        {
            "question": "What is your return policy?"
        },
        validation_mode="rag",
        max_retries=1,
    )

    assert result["status"] == "PASS"
    assert len(result["attempts"]) == 2

    assert result["attempts"][0]["review"]["status"] == "REJECTED"
    assert result["attempts"][1]["review"]["status"] == "APPROVED"

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

    def fake_act(ticket, evidence, correction=""):
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

    def fake_act(ticket, evidence, correction=""):
        return {
            "answer": "Some answer",
        }

    def fake_review(ticket, evaluation, evidence):
        raise AssertionError(
            "Review should not be called for invalid ACT output."
        )

    monkeypatch.setattr(loop, "rag_validate", fake_rag_validate)
    monkeypatch.setattr(loop, "act", fake_act)
    monkeypatch.setattr(loop, "review", fake_review)

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
        result["attempts"][0]["review"]["status"]
        == "REJECTED"
    )

    assert (
        "required fields"
        in result["attempts"][0]["review"]["feedback"]
    )