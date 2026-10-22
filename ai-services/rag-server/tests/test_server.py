import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import server  # noqa: E402


@pytest.fixture
def client():
    server.app.testing = True
    return server.app.test_client()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["chunks_loaded"] > 0


def test_query_requires_query_field(client):
    resp = client.post("/rag/query", json={})
    assert resp.status_code == 400


def test_query_returns_insufficient_context_for_unrelated_question(client):
    resp = client.post("/rag/query", json={"query": "xyz completely unrelated zzz qqq"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["insufficient_context"] is True


def test_query_returns_grounded_answer_with_citations(client, monkeypatch):
    def _fake_generate(query, chunks):
        return "Standard shipping is free over $75."
    monkeypatch.setattr(server, "generate", _fake_generate)

    resp = client.post("/rag/query", json={"query": "how much is standard shipping"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert "insufficient_context" not in body
    assert body["answer"] == "Standard shipping is free over $75."
    assert body["confidence"] in {"high", "medium", "low"}
    assert body["citations"]
    assert body["citations"][0]["source"] == "shipping-and-returns.md"


def test_query_falls_back_to_excerpt_when_ollama_unreachable(client, monkeypatch):
    def _boom(query, chunks):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(server, "generate", _boom)

    resp = client.post("/rag/query", json={"query": "how do I file a warranty claim"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert "warranty-policy.md" in body["answer"]
    assert body["confidence"] == "low"


def test_extract_answer_falls_back_when_model_output_is_not_json():
    chunks = [{"source": "x.md", "heading": "H", "text": "excerpt text"}]
    answer = server._extract_answer("not json at all", chunks)
    assert "excerpt text" in answer


def test_retrieve_returns_chunks_without_calling_ollama(client, monkeypatch):
    def _boom(query, chunks):
        raise AssertionError("retrieve must not call Ollama")
    monkeypatch.setattr(server, "generate", _boom)

    resp = client.post("/rag/retrieve", json={"query": "power point 10A kitchen appliances together", "limit": 2})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["insufficient_context"] is False
    assert 1 <= len(body["chunks"]) <= 2
    assert body["chunks"][0]["source"] == "appliance-installation-and-cart.md"
    assert body["chunks"][0]["text"]


def test_retrieve_requires_query_and_reports_no_match(client):
    assert client.post("/rag/retrieve", json={}).status_code == 400
    body = client.post("/rag/retrieve", json={"query": "xyz completely unrelated zzz qqq"}).get_json()
    assert body["insufficient_context"] is True
    assert body["chunks"] == []
