"""
Release 1 tests for the Store policy (RAG) card: POST /api/rag/ask asks the
shared RAG server (POST /rag/query) and shows its grounded answer, citations
and confidence, or the insufficient-context message.

No RAG server needed: requests.post is replaced with a fake, so this runs in CI.
"""

import os
import sys

import pytest
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
sys.path.insert(0, os.path.join(HERE, "..", "database"))

import agent  # noqa: E402
import main  # noqa: E402

GROUNDED = {
    "answer": "Items can be returned within **30 days** of delivery for a full refund.",
    "citations": [{"source": "shipping-and-returns.md", "section": "Return Window",
                   "snippet": "Items can be returned within 30 days of delivery..."}],
    "confidence": "high",
}
NOTHING = {"insufficient_context": True, "message": "I don't have enough information to answer that yet."}


class FakeResponse:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


# FIXTURE: RAG on, fake RAG server that records each call
@pytest.fixture
def client(monkeypatch):
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append((url, json))
        return FakeResponse(NOTHING if "football" in json["query"] else GROUNDED)

    monkeypatch.setattr(agent, "RAG_ENABLED", True)
    monkeypatch.setattr(main.requests, "post", fake_post)
    main.app.testing = True
    c = main.app.test_client()
    c.calls = calls
    return c


def test_grounded_answer_with_citations_and_confidence(client):
    html = client.post("/api/rag/ask", data={"question": "What is your return policy?"}).get_data(as_text=True)
    assert client.calls == [(agent.RAG_HOST + "/rag/query", {"query": "What is your return policy?"})]
    assert "ai-alert-box success" in html
    assert "<strong>30 days</strong>" in html                       # markdown bold rendered safely
    assert "shipping-and-returns.md › Return Window" in html        # citation
    assert "rag-badge high" in html and "Confidence: high" in html  # confidence category


def test_insufficient_context(client):
    html = client.post("/api/rag/ask", data={"question": "Who won the football last night?"}).get_data(as_text=True)
    assert "ai-alert-box warning" in html
    assert "enough information" in html and "Insufficient context" in html
    assert "Confidence:" not in html                                # no made-up answer


def test_json_mode_returns_rag_body(client):
    body = client.post("/api/rag/ask", json={"question": "What is your return policy?"}).get_json()
    assert body["confidence"] == "high" and body["citations"]


def test_rag_server_offline(client, monkeypatch):
    def down(url, json=None, timeout=None):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(main.requests, "post", down)
    html = client.post("/api/rag/ask", data={"question": "Returns?"}).get_data(as_text=True)
    assert "ai-alert-box error" in html and "RAG server offline" in html


def test_empty_question_and_disabled(client, monkeypatch):
    assert "Please type a question" in client.post("/api/rag/ask", data={"question": " "}).get_data(as_text=True)
    monkeypatch.setattr(agent, "RAG_ENABLED", False)
    html = client.post("/api/rag/ask", data={"question": "Returns?"}).get_data(as_text=True)
    assert "RAG is disabled" in html and client.calls == []


def test_answer_html_is_escaped(client, monkeypatch):
    monkeypatch.setattr(main.requests, "post",
                        lambda url, json=None, timeout=None: FakeResponse({**GROUNDED, "answer": "<script>x</script>"}))
    html = client.post("/api/rag/ask", data={"question": "Returns?"}).get_data(as_text=True)
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_page_has_rag_card(client):
    html = client.get("/").get_data(as_text=True)
    assert 'hx-post="/api/rag/ask"' in html and "Store policy" in html
