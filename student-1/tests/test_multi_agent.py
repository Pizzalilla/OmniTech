"""Planner, Worker, Reviewer, and the human decision. The shared server is faked."""

import requests

import backend.multi_agent_client as multi_agent_client

WF_ID = "wf-1234abcd"


def _app():
    import backend.app as catalog_app

    return catalog_app


def _workflow(status="awaiting_human", **extra):
    workflow = {
        "id": WF_ID,
        "student": "student-1",
        "status": status,
        "plan": {
            "goal": "Check the listing stays inside the stored specs",
            "steps": ["Read the specifications"],
            "evidence_needed": ["product", "specifications"],
            "missing_evidence": [],
        },
        "work": {
            "answer": "A compact fridge with a 320 L capacity.",
            "steps_done": [],
            "evidence_used": ["product", "specifications"],
            "issues": [],
        },
        "review": {
            "verdict": "pass",
            "summary": "The description matches the stored specifications.",
            "risks": [],
            "recommendations": [],
            "checks": [],
        },
        "human": None,
        "final_answer": None,
    }
    workflow.update(extra)
    return workflow


def _decided(decision, status, final_answer):
    return _workflow(
        status,
        final_answer=final_answer,
        human={"decision": decision, "reviewer": "staff", "note": "", "decided_at": "now"},
    )


def test_product_page_offers_a_review(client):
    page = client.get("/products/1")
    assert page.status_code == 200
    assert b"Review this listing" in page.data
    assert b"Review history" in page.data


def test_review_sends_product_specs_and_policy(client, monkeypatch):
    sent = {}

    def _start(task, evidence):
        sent.update(task=task, evidence=evidence)
        return _workflow()

    monkeypatch.setattr(_app(), "RAG_ENABLED", True)
    monkeypatch.setattr(multi_agent_client, "start", _start)
    monkeypatch.setattr(
        _app().rag_client,
        "retrieve",
        lambda query, limit=2: [{"source": "warranty.md", "heading": "Warranty", "text": "12 months."}],
    )

    response = client.post("/api/products/1/multi-agent-review")
    assert response.status_code == 201
    assert response.get_json()["status"] == "awaiting_human"
    assert sent["evidence"]["product"]["id"] == 1
    assert sent["evidence"]["specifications"]
    assert sent["evidence"]["store_policy"][0]["source"] == "warranty.md"


def test_review_still_runs_when_rag_is_down(client, monkeypatch):
    sent = {}

    def _rag_down(query, limit=2):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(_app(), "RAG_ENABLED", True)
    monkeypatch.setattr(_app().rag_client, "retrieve", _rag_down)
    monkeypatch.setattr(
        multi_agent_client,
        "start",
        lambda task, evidence: sent.update(evidence=evidence) or _workflow(),
    )
    assert client.post("/api/products/1/multi-agent-review").status_code == 201
    assert "store_policy" not in sent["evidence"]


def test_review_page_shows_the_four_steps(client, monkeypatch):
    monkeypatch.setattr(_app(), "RAG_ENABLED", False)
    monkeypatch.setattr(multi_agent_client, "start", lambda task, evidence: _workflow())
    response = client.post("/api/products/1/multi-agent-review", headers={"HX-Request": "true"})
    assert response.status_code == 200
    for text in (b"Planner", b"Worker", b"Reviewer", b"Human review", b"Approve", b"Reject"):
        assert text in response.data


def test_review_unknown_product(client):
    assert client.post("/api/products/99999/multi-agent-review").status_code == 404


def test_review_server_offline(client, monkeypatch):
    def _down(task, evidence):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(_app(), "RAG_ENABLED", False)
    monkeypatch.setattr(multi_agent_client, "start", _down)
    response = client.post("/api/products/1/multi-agent-review")
    assert response.status_code == 503
    assert "not reachable" in response.get_json()["error"]
    assert client.get("/api/products/1").status_code == 200


def test_review_when_agents_cannot_reach_ollama(client, monkeypatch):
    monkeypatch.setattr(_app(), "RAG_ENABLED", False)
    monkeypatch.setattr(
        multi_agent_client,
        "start",
        lambda task, evidence: _workflow(
            "failed", plan=None, work=None, review=None, error="Ollama is not reachable"
        ),
    )
    response = client.post("/api/products/1/multi-agent-review", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert b"Ollama is not reachable" in response.data


def test_review_disabled_keeps_the_catalog_up(client, monkeypatch):
    monkeypatch.setattr(_app(), "MULTI_AGENT_ENABLED", False)
    response = client.post("/api/products/1/multi-agent-review")
    assert response.status_code == 503
    assert "disabled" in response.get_json()["error"]
    assert client.get("/").status_code == 200


def test_approve_saves_the_description(client, monkeypatch):
    monkeypatch.setattr(
        multi_agent_client,
        "decide",
        lambda *args, **kwargs: _decided("approve", "approved", "A compact fridge with a 320 L capacity."),
    )
    response = client.post(
        "/api/multi-agent/decision",
        json={"workflow_id": WF_ID, "product_id": 1, "decision": "approve", "reviewer": "kris"},
    )
    assert response.status_code == 200
    assert response.get_json()["product"]["description"] == "A compact fridge with a 320 L capacity."
    assert client.get("/api/products/1").get_json()["description"] == "A compact fridge with a 320 L capacity."


def test_correct_updates_the_description_on_the_page(client, monkeypatch):
    monkeypatch.setattr(
        multi_agent_client,
        "decide",
        lambda *args, **kwargs: _decided("correct", "corrected", "Corrected listing text"),
    )
    response = client.post(
        "/api/multi-agent/decision",
        headers={"HX-Request": "true"},
        data={
            "workflow_id": WF_ID,
            "product_id": "1",
            "decision": "correct",
            "corrected_answer": "Corrected listing text",
        },
    )
    assert response.status_code == 200
    assert b"Corrected listing text" in response.data
    assert b'id="product-description"' in response.data
    assert client.get("/api/products/1").get_json()["description"] == "Corrected listing text"


def test_partial_saves_the_worker_answer(client, monkeypatch):
    monkeypatch.setattr(
        multi_agent_client,
        "decide",
        lambda *args, **kwargs: _decided("partial", "partially_accepted", "A compact fridge with a 320 L capacity."),
    )
    response = client.post(
        "/api/multi-agent/decision",
        json={"workflow_id": WF_ID, "product_id": 1, "decision": "partial", "note": "price left out"},
    )
    assert response.status_code == 200
    stored = client.get("/api/products/1").get_json()
    assert stored["description"] == "A compact fridge with a 320 L capacity."


def test_reject_keeps_the_description(client, monkeypatch):
    before = client.get("/api/products/1").get_json()["description"]
    monkeypatch.setattr(
        multi_agent_client,
        "decide",
        lambda *args, **kwargs: _decided("reject", "rejected", None),
    )
    response = client.post(
        "/api/multi-agent/decision",
        headers={"HX-Request": "true"},
        data={"workflow_id": WF_ID, "product_id": "1", "decision": "reject", "note": "invented a feature"},
    )
    assert response.status_code == 200
    assert b"unchanged" in response.data
    assert client.get("/api/products/1").get_json()["description"] == before


def test_missing_note_shows_the_form_again(client, monkeypatch):
    def _decide(*args, **kwargs):
        raise multi_agent_client.MultiAgentError("a note is required when the decision is 'reject'")

    monkeypatch.setattr(multi_agent_client, "decide", _decide)
    monkeypatch.setattr(multi_agent_client, "get", lambda workflow_id: _workflow())
    response = client.post(
        "/api/multi-agent/decision",
        headers={"HX-Request": "true"},
        data={"workflow_id": WF_ID, "product_id": "1", "decision": "reject"},
    )
    assert b"a note is required" in response.data
    assert b"Approve" in response.data


def test_bad_workflow_id_is_rejected(client):
    response = client.post(
        "/api/multi-agent/decision",
        json={"workflow_id": "../../etc", "decision": "approve"},
    )
    assert response.status_code == 400


def test_history_lists_this_features_workflows(client, monkeypatch):
    monkeypatch.setattr(
        multi_agent_client,
        "history",
        lambda limit=5: [{"id": WF_ID, "status": "approved", "created_at": "now"}],
    )
    response = client.get("/api/multi-agent/history", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert WF_ID.encode() in response.data


def test_history_disabled(client, monkeypatch):
    monkeypatch.setattr(_app(), "MULTI_AGENT_ENABLED", False)
    response = client.get("/api/multi-agent/history")
    assert response.status_code == 503
    assert "disabled" in response.get_json()["error"]


def test_client_names_student_1(monkeypatch):
    captured = {}

    class _Resp:
        status_code = 201

        def json(self):
            return _workflow()

    def _post(url, json=None, timeout=None):
        captured.update(url=url, body=json)
        return _Resp()

    monkeypatch.setattr(multi_agent_client.requests, "post", _post)
    multi_agent_client.start("task", {"product": {}})
    assert captured["url"].endswith("/workflow/start")
    assert captured["body"]["student"] == "student-1"
