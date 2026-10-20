"""Integration with the shared Release 2 Multi-Agent server (faked here)."""

import json

import pytest
import requests

import main
import multi_agent_client

WF_ID = "wf-1234abcd"


def _workflow(status="awaiting_human", **extra):
    wf = {
        "id": WF_ID, "student": "student-3", "status": status,
        "plan": {"goal": "Check the laptop fits", "steps": ["Compare budget"],
                 "evidence_needed": ["recommendation"], "missing_evidence": []},
        "work": {"answer": "The Meridian Pro 16 (LAP-001) fits 4K editing.",
                 "steps_done": [], "evidence_used": ["recommendation"], "issues": []},
        "review": {"verdict": "pass", "summary": "Grounded in the evidence.",
                   "risks": [], "recommendations": [], "checks": []},
        "human": None, "final_answer": None,
    }
    wf.update(extra)
    return wf


def _decided(decision, status, final_answer):
    return _workflow(status, final_answer=final_answer, human={
        "decision": decision, "reviewer": "staff", "note": "", "decided_at": "now"})


@pytest.fixture
def first_reco_id(client):
    return json.loads(client.get("/api/sessions/1/recommendations").data)[0]["id"]


def test_review_sends_recommendation_and_customer_requests(client, monkeypatch, first_reco_id):
    sent = {}

    def _start(task, evidence):
        sent.update(task=task, evidence=evidence)
        return _workflow()
    monkeypatch.setattr(multi_agent_client, "start", _start)
    monkeypatch.setattr(main.rag_client, "retrieve", lambda q, limit=3: [
        {"source": "warranty.md", "heading": "Warranty", "text": "12 months."}])

    rv = client.post(f"/api/recommendations/{first_reco_id}/multi-agent-review")
    assert rv.status_code == 201
    assert json.loads(rv.data)["status"] == "awaiting_human"
    evidence = sent["evidence"]
    assert evidence["recommendation"]["products"]
    assert evidence["customer_requests"]
    assert evidence["store_policy"][0]["source"] == "warranty.md"
    rec_ids = {p["id"] for p in evidence["recommendation"]["products"]}
    assert not rec_ids & {p["id"] for p in evidence["other_catalog_matches"]}


def test_review_runs_without_rag(client, monkeypatch, first_reco_id):
    def _rag_down(q, limit=3):
        raise requests.ConnectionError("refused")
    sent = {}
    monkeypatch.setattr(main.rag_client, "retrieve", _rag_down)
    monkeypatch.setattr(multi_agent_client, "start",
                        lambda task, evidence: sent.update(evidence=evidence) or _workflow())
    assert client.post(f"/api/recommendations/{first_reco_id}/multi-agent-review").status_code == 201
    assert "store_policy" not in sent["evidence"]


def test_review_htmx_shows_three_agents_and_decision_buttons(client, monkeypatch, first_reco_id):
    monkeypatch.setattr(main, "RAG_ENABLED", False)
    monkeypatch.setattr(multi_agent_client, "start", lambda task, evidence: _workflow())
    rv = client.post(f"/api/recommendations/{first_reco_id}/multi-agent-review",
                     headers={"HX-Request": "true"})
    assert rv.status_code == 200
    for text in (b"Planner", b"Worker", b"Reviewer", b"Human review", b"Approve", b"Reject", WF_ID.encode()):
        assert text in rv.data


def test_review_flags_unknown_product_ids(client, monkeypatch, first_reco_id):
    monkeypatch.setattr(main, "RAG_ENABLED", False)
    bad = _workflow(work={"answer": "Try the ZZZ-999.", "evidence_used": [], "issues": []})
    monkeypatch.setattr(multi_agent_client, "start", lambda task, evidence: bad)
    rv = client.post(f"/api/recommendations/{first_reco_id}/multi-agent-review",
                     headers={"HX-Request": "true"})
    assert b"ZZZ-999" in rv.data and b"not in the catalog" in rv.data


def test_review_unknown_recommendation_404(client):
    assert client.post("/api/recommendations/9999/multi-agent-review").status_code == 404


def test_review_server_offline(client, monkeypatch, first_reco_id):
    def _down(task, evidence):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(main, "RAG_ENABLED", False)
    monkeypatch.setattr(multi_agent_client, "start", _down)
    rv = client.post(f"/api/recommendations/{first_reco_id}/multi-agent-review")
    assert rv.status_code == 503
    assert "not reachable" in json.loads(rv.data)["error"]


def test_review_agents_failed_because_ollama_is_down(client, monkeypatch, first_reco_id):
    monkeypatch.setattr(main, "RAG_ENABLED", False)
    monkeypatch.setattr(multi_agent_client, "start", lambda task, evidence: _workflow(
        "failed", plan=None, work=None, review=None, error="Ollama is not reachable"))
    rv = client.post(f"/api/recommendations/{first_reco_id}/multi-agent-review",
                     headers={"HX-Request": "true"})
    assert rv.status_code == 200
    assert b"failed" in rv.data and b"Ollama is not reachable" in rv.data


def test_review_disabled(client, monkeypatch, first_reco_id):
    monkeypatch.setattr(main, "MULTI_AGENT_ENABLED", False)
    rv = client.post(f"/api/recommendations/{first_reco_id}/multi-agent-review")
    assert rv.status_code == 503
    assert "disabled" in json.loads(rv.data)["error"]


def test_approve_saves_final_answer_and_tag(client, monkeypatch, first_reco_id):
    sent = {}

    def _decide(workflow_id, decision, **kw):
        sent.update(workflow_id=workflow_id, decision=decision, **kw)
        return _decided("approve", "approved", "The Meridian Pro 16 (LAP-001) fits 4K editing.")
    monkeypatch.setattr(multi_agent_client, "decide", _decide)

    rv = client.post("/api/multi-agent/decision", json={
        "workflow_id": WF_ID, "reco_id": first_reco_id, "decision": "approve", "reviewer": "kartikay"})
    assert rv.status_code == 200
    assert sent["workflow_id"] == WF_ID and sent["reviewer"] == "kartikay"
    reco = json.loads(rv.data)["recommendation"]
    assert reco["summary"] == "The Meridian Pro 16 (LAP-001) fits 4K editing."
    assert "agent-approved" in reco["tags"]


def test_reject_keeps_summary_and_replaces_old_agent_tag(client, monkeypatch, first_reco_id):
    monkeypatch.setattr(multi_agent_client, "decide",
                        lambda *a, **kw: _decided("approve", "approved", "Approved text"))
    client.post("/api/multi-agent/decision",
                json={"workflow_id": WF_ID, "reco_id": first_reco_id, "decision": "approve"})
    monkeypatch.setattr(multi_agent_client, "decide",
                        lambda *a, **kw: _decided("reject", "rejected", None))
    reco = json.loads(client.post("/api/multi-agent/decision", json={
        "workflow_id": WF_ID, "reco_id": first_reco_id, "decision": "reject", "note": "wrong budget",
    }).data)["recommendation"]
    assert reco["summary"] == "Approved text"
    assert "agent-rejected" in reco["tags"] and "agent-approved" not in reco["tags"]


def test_decision_htmx_updates_reco_card_out_of_band(client, monkeypatch, first_reco_id):
    monkeypatch.setattr(multi_agent_client, "decide",
                        lambda *a, **kw: _decided("correct", "corrected", "Corrected text"))
    rv = client.post("/api/multi-agent/decision", headers={"HX-Request": "true"}, data={
        "workflow_id": WF_ID, "reco_id": str(first_reco_id), "decision": "correct",
        "corrected_answer": "Corrected text"})
    assert rv.status_code == 200
    assert b"corrected" in rv.data
    assert f'id="reco-{first_reco_id}"'.encode() in rv.data and b'hx-swap-oob="true"' in rv.data


def test_decision_error_shows_workflow_again(client, monkeypatch):
    def _decide(*a, **kw):
        raise multi_agent_client.MultiAgentError("a note is required when the decision is 'reject'")
    monkeypatch.setattr(multi_agent_client, "decide", _decide)
    monkeypatch.setattr(multi_agent_client, "get", lambda wid: _workflow())
    rv = client.post("/api/multi-agent/decision", headers={"HX-Request": "true"},
                     data={"workflow_id": WF_ID, "decision": "reject"})
    assert b"a note is required" in rv.data and b"Approve" in rv.data


def test_decision_rejects_bad_workflow_id(client):
    rv = client.post("/api/multi-agent/decision", json={"workflow_id": "../../etc", "decision": "approve"})
    assert rv.status_code == 400


def test_history_lists_student3_workflows(client, monkeypatch):
    seen = {}

    def _history(limit=5):
        seen["limit"] = limit
        return [{"id": WF_ID, "status": "approved", "reviewer_verdict": "pass", "created_at": "now"}]
    monkeypatch.setattr(multi_agent_client, "history", _history)
    rv = client.get("/api/multi-agent/history", headers={"HX-Request": "true"})
    assert rv.status_code == 200 and WF_ID.encode() in rv.data and seen["limit"] == 5


def test_history_disabled(client, monkeypatch):
    monkeypatch.setattr(main, "MULTI_AGENT_ENABLED", False)
    assert client.get("/api/multi-agent/history").status_code == 503


def test_client_sends_student_id(monkeypatch):
    captured = {}

    class _Resp:
        status_code = 201

        def json(self):
            return _workflow()

    def _post(url, json=None, timeout=None):
        captured.update(url=url, body=json)
        return _Resp()
    monkeypatch.setattr(multi_agent_client.requests, "post", _post)
    multi_agent_client.start("task", {"recommendation": {}})
    assert captured["url"].endswith("/workflow/start")
    assert captured["body"]["student"] == "student-3"
