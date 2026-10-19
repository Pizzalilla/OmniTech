"""
Release 2 tests for the Cart review (Multi-Agent) card.

POST /api/multi-agent/review-cart sends the cart evidence to the shared
Multi-Agent server and shows the Planner / Worker / Reviewer output.
POST /api/multi-agent/decision passes the human decision back.

No servers needed: requests.post / requests.get are faked, so this runs in CI.
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

WF_ID = "wf-1a2b3c4d"


def workflow(status="awaiting_human", human=None, final=None):
    return {
        "id": WF_ID,
        "student": "student-4",
        "status": status,
        "plan": {"goal": "Check the cart", "steps": ["Read cart", "Check stock"],
                 "evidence_needed": ["cart"], "success_criteria": [], "missing_evidence": []},
        "work": {"answer": "Microwave is **out of stock**.", "steps_done": [], "evidence_used": ["cart"], "issues": []},
        "review": {"verdict": "needs_changes", "summary": "Mention the power point limit.",
                   "risks": ["Overloaded 10A socket"], "recommendations": ["Add a power warning"], "checks": []},
        "human": human,
        "final_answer": final,
    }


class FakeResponse:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def json(self):
        return self._body


# FIXTURE: multi-agent on, MCP/RAG off, fake server that records each call
@pytest.fixture
def client(monkeypatch):
    calls = []
    replies = {"start": (workflow(), 201), "decision": None, "get": (workflow(), 200)}

    def fake_post(url, json=None, timeout=None):
        calls.append((url, json))
        if url.endswith("/workflow/start"):
            body, status = replies["start"]
        else:
            if replies["decision"]:
                body, status = replies["decision"]
            else:
                human = {"decision": json["decision"], "reviewer": json["reviewer"], "note": json["note"],
                         "decided_at": "2026-10-19T05:00:00+00:00"}
                final = None if json["decision"] == "reject" else "Microwave is **out of stock**."
                status_name = {"approve": "approved", "correct": "corrected",
                               "partial": "partially_accepted", "reject": "rejected"}[json["decision"]]
                body, status = workflow(status_name, human, final), 200
        return FakeResponse(body, status)

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params))
        if url.endswith("/workflows"):
            return FakeResponse({"workflows": [{"id": WF_ID, "created_at": "2026-10-19", "reviewer_verdict": "pass",
                                                "status": "approved"}]})
        return FakeResponse(*replies["get"])

    monkeypatch.setattr(agent, "MULTI_AGENT_ENABLED", True)
    monkeypatch.setattr(agent, "MCP_ENABLED", False)
    monkeypatch.setattr(agent, "RAG_ENABLED", False)
    monkeypatch.setattr(main.requests, "post", fake_post)
    monkeypatch.setattr(main.requests, "get", fake_get)
    monkeypatch.setattr(main, "CUSTOMER_CART", {**main.CUSTOMER_CART, "items": [dict(i) for i in main.DEMO_CART_ITEMS]})
    main.app.testing = True
    c = main.app.test_client()
    c.calls, c.replies = calls, replies
    return c


def test_review_sends_cart_evidence_and_shows_all_three_agents(client):
    html = client.post("/api/multi-agent/review-cart", data={"task": ""}).get_data(as_text=True)

    url, sent = client.calls[0]
    assert url == agent.MULTI_AGENT_HOST + "/workflow/start"
    assert sent["student"] == "student-4" and sent["task"] == main.DEFAULT_REVIEW_TASK
    assert {"cart", "product_specs", "safety_checks"} <= set(sent["evidence"])
    assert sent["evidence"]["cart"]["items"][0]["product_name"] == "Samsung Fridge 500L"

    assert "1 · Planner" in html and "2 · Worker" in html and "3 · Reviewer" in html
    assert "<strong>out of stock</strong>" in html                      # markdown bold rendered safely
    assert "needs changes" in html and "Overloaded 10A socket" in html
    assert "4 · Human review" in html and WF_ID in html
    for value in ("approve", "correct", "partial", "reject"):
        assert f'"decision": "{value}"' in html


def test_custom_task_is_passed_through(client):
    client.post("/api/multi-agent/review-cart", data={"task": "Check the power points"})
    assert client.calls[0][1]["task"] == "Check the power points"


def test_json_mode_returns_server_body(client):
    resp = client.post("/api/multi-agent/review-cart", json={})
    assert resp.status_code == 201 and resp.get_json()["id"] == WF_ID


def test_approve_shows_final_answer(client):
    html = client.post("/api/multi-agent/decision",
                       data={"workflow_id": WF_ID, "decision": "approve", "reviewer": "sky"}).get_data(as_text=True)
    url, sent = client.calls[0]
    assert url == f"{agent.MULTI_AGENT_HOST}/workflow/{WF_ID}/decision"
    assert sent["decision"] == "approve" and sent["reviewer"] == "sky"
    assert "approved" in html and "Final answer" in html and "By:</strong> sky" in html


def test_reject_shows_nothing_to_customer(client):
    html = client.post("/api/multi-agent/decision",
                       data={"workflow_id": WF_ID, "decision": "reject", "note": "Wrong total"}).get_data(as_text=True)
    assert "rejected" in html and "nothing is shown to the customer" in html and "Wrong total" in html


def test_missing_note_shows_the_form_again_with_the_error(client):
    client.replies["decision"] = ({"error": "a note is required when the decision is 'partial'"}, 400)
    html = client.post("/api/multi-agent/decision",
                       data={"workflow_id": WF_ID, "decision": "partial"}).get_data(as_text=True)
    assert "a note is required" in html and "4 · Human review" in html and "Approve" in html


def test_already_decided(client):
    client.replies["decision"] = ({"error": "workflow is 'approved', not waiting for a human decision"}, 409)
    html = client.post("/api/multi-agent/decision",
                       data={"workflow_id": WF_ID, "decision": "approve"}).get_data(as_text=True)
    assert "ai-alert-box error" in html and "not waiting" in html


def test_bad_workflow_id_never_reaches_the_server(client):
    html = client.post("/api/multi-agent/decision",
                       data={"workflow_id": "../../admin", "decision": "approve"}).get_data(as_text=True)
    assert "Unknown workflow id" in html and client.calls == []


def test_agents_failed_because_ollama_is_down(client):
    client.replies["start"] = ({"status": "failed", "error": "Ollama call failed: refused"}, 503)
    html = client.post("/api/multi-agent/review-cart", data={}).get_data(as_text=True)
    assert "ai-alert-box error" in html and "Ollama" in html


def test_server_offline(client, monkeypatch):
    def down(url, json=None, timeout=None):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(main.requests, "post", down)
    html = client.post("/api/multi-agent/review-cart", data={}).get_data(as_text=True)
    assert "Multi-Agent server offline" in html


def test_disabled_in_cloud(client, monkeypatch):
    monkeypatch.setattr(agent, "MULTI_AGENT_ENABLED", False)
    html = client.post("/api/multi-agent/review-cart", data={}).get_data(as_text=True)
    assert "turned off in this deployment" in html and client.calls == []
    assert client.post("/api/multi-agent/review-cart", json={}).status_code == 503


def test_empty_cart(client):
    main.CUSTOMER_CART["items"] = []
    html = client.post("/api/multi-agent/review-cart", data={}).get_data(as_text=True)
    assert "cart is empty" in html and client.calls == []


def test_agent_output_is_escaped(client):
    bad = workflow()
    bad["work"]["answer"] = "<script>alert(1)</script>"
    bad["review"]["summary"] = "<img src=x onerror=alert(1)>"
    client.replies["start"] = (bad, 201)
    html = client.post("/api/multi-agent/review-cart", data={}).get_data(as_text=True)
    assert "<script>" not in html and "<img" not in html and "&lt;script&gt;" in html


def test_history(client):
    html = client.get("/api/multi-agent/history").get_data(as_text=True)
    assert WF_ID in html and "approved" in html
    assert client.calls[0][1] == {"student": "student-4", "limit": 5}


def test_page_has_multi_agent_card(client):
    html = client.get("/").get_data(as_text=True)
    assert 'hx-post="/api/multi-agent/review-cart"' in html and "Cart review" in html
