"""
Tests for the Multi-Agent Server. Ollama is faked, so nothing else needs
to be running - safe for GitHub Actions.
"""

import json
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import agents  # noqa: E402
import audit  # noqa: E402
import cli  # noqa: E402
import server  # noqa: E402
import workflow as wf  # noqa: E402

EVIDENCE = {
    "cart": {"items": [{"product_id": 3, "name": "Dishwasher", "qty": 1, "price": 899.0}], "total": 899.0},
    "stock": {"3": 4},
}


# FAKE OLLAMA: answers depend on which agent is asking
def fake_reply(system_prompt, user_prompt):
    if "Reviewer agent" in system_prompt:
        return {"verdict": "pass", "summary": "Matches the evidence.", "risks": [], "recommendations": []}
    if "Planner agent" in system_prompt:
        return {"goal": "Check the cart", "steps": ["Read cart", "Check stock", "Write summary"],
                "evidence_needed": ["cart", "stock"], "success_criteria": ["Uses real prices"]}
    if "Worker" in system_prompt:
        return {"answer": "1 x Dishwasher at $899.00, 4 in stock. Ready for checkout.",
                "steps_done": ["Read cart", "Checked stock", "Wrote summary"],
                "evidence_used": ["cart", "stock"], "issues": []}


@pytest.fixture(autouse=True)
def temp_logs(tmp_path, monkeypatch):
    # every test gets its own empty log folder
    monkeypatch.setattr(audit, "LOG_DIR", tmp_path)
    monkeypatch.setattr(audit, "AUDIT_FILE", tmp_path / "audit.jsonl")
    monkeypatch.setattr(audit, "HISTORY_DIR", tmp_path / "history")


@pytest.fixture
def fake_ollama(monkeypatch):
    monkeypatch.setattr(agents, "ask_ollama", fake_reply)


@pytest.fixture
def client():
    server.app.config["TESTING"] = True
    return server.app.test_client()


def started():
    return wf.start_workflow("student-4", "Check this cart before checkout", EVIDENCE)


# ---------------------------------------------------------------------------
# agents
# ---------------------------------------------------------------------------

def test_parse_json_cuts_out_wrapped_object():
    assert agents.parse_json('Sure! {"a": 1} hope that helps') == {"a": 1}


def test_parse_json_rejects_garbage():
    with pytest.raises(agents.AgentError):
        agents.parse_json("no json here")


def test_planner_fills_defaults_and_flags_missing_evidence(monkeypatch):
    monkeypatch.setattr(agents, "ask_ollama",
                        lambda s, u: {"steps": "Read cart", "evidence_needed": ["cart", "warranty"]})
    plan = agents.planner("Check cart", EVIDENCE)
    assert plan["steps"] == ["Read cart"]
    assert plan["goal"] == "Check cart"
    assert plan["missing_evidence"] == ["warranty"]


def test_planner_with_no_steps_is_an_error(monkeypatch):
    monkeypatch.setattr(agents, "ask_ollama", lambda s, u: {"goal": "x"})
    with pytest.raises(agents.AgentError):
        agents.planner("Check cart", EVIDENCE)


def test_reviewer_downgrades_pass_when_worker_cites_unknown_evidence(monkeypatch):
    monkeypatch.setattr(agents, "ask_ollama", lambda s, u: {"verdict": "PASS", "summary": "ok"})
    plan = {"steps": ["a"], "missing_evidence": []}
    work = {"answer": "x", "steps_done": [], "evidence_used": ["cart", "made_up_prices"], "issues": []}
    review = agents.reviewer("t", plan, EVIDENCE, work)
    assert review["verdict"] == "needs_changes"
    assert "made_up_prices" in review["checks"][0]


def test_reviewer_unknown_verdict_becomes_needs_changes(monkeypatch):
    monkeypatch.setattr(agents, "ask_ollama", lambda s, u: {"verdict": "looks fine"})
    plan = {"steps": ["a"], "missing_evidence": []}
    work = {"answer": "x", "steps_done": [], "evidence_used": [], "issues": []}
    assert agents.reviewer("t", plan, EVIDENCE, work)["verdict"] == "needs_changes"


def test_ollama_url_handles_windows_listen_address():
    assert agents.ollama_url("0.0.0.0:11434") == "http://127.0.0.1:11434"
    assert agents.ollama_url("http://host.docker.internal:11434/") == "http://host.docker.internal:11434"
    assert agents.ollama_url(None) == "http://127.0.0.1:11434"


def test_ollama_down_raises_agent_error(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(agents.requests, "post", boom)
    with pytest.raises(agents.AgentError):
        agents.ask_ollama("sys", "user")


# ---------------------------------------------------------------------------
# workflow + audit
# ---------------------------------------------------------------------------

def test_full_run_stops_at_human_and_logs_every_step(fake_ollama):
    item = started()
    assert item["status"] == "awaiting_human"
    assert item["plan"]["steps"] and item["work"]["answer"] and item["review"]["verdict"] == "pass"

    actions = [e["action"] for e in audit.read_events(item["id"])]
    assert actions == ["workflow_started", "plan_created", "task_completed",
                       "review_completed", "awaiting_human_review"]
    assert audit.load_workflow(item["id"])["status"] == "awaiting_human"


def test_failed_run_is_saved_with_the_error(monkeypatch):
    def down(s, u):
        raise agents.AgentError("Ollama call failed: refused")
    monkeypatch.setattr(agents, "ask_ollama", down)
    item = started()
    assert item["status"] == "failed"
    assert "refused" in item["error"]
    assert audit.read_events(item["id"])[-1]["action"] == "workflow_failed"


@pytest.mark.parametrize("bad", [
    ("", "task", EVIDENCE),
    ("student-4", "", EVIDENCE),
    ("student-4", "task", {}),
    ("student-4", "task", ["not", "a", "dict"]),
    ("student-4", "x" * 2001, EVIDENCE),
])
def test_bad_start_input_is_rejected(bad):
    with pytest.raises(ValueError):
        wf.start_workflow(*bad)


def test_approve_uses_worker_answer(fake_ollama):
    item = started()
    done = wf.apply_decision(item["id"], "approve", reviewer="sky")
    assert done["status"] == "approved"
    assert done["final_answer"] == item["work"]["answer"]
    assert done["human"]["agreed_with_reviewer"] is True
    assert audit.read_events(item["id"])[-1]["actor"] == "human:sky"


def test_correct_needs_and_uses_corrected_answer(fake_ollama):
    item = started()
    with pytest.raises(ValueError):
        wf.apply_decision(item["id"], "correct")
    done = wf.apply_decision(item["id"], "correct", corrected_answer="Price is $849 on sale.")
    assert done["status"] == "corrected"
    assert done["final_answer"] == "Price is $849 on sale."


def test_partial_and_reject_need_a_note(fake_ollama):
    first, second = started(), started()
    with pytest.raises(ValueError):
        wf.apply_decision(first["id"], "partial")
    with pytest.raises(ValueError):
        wf.apply_decision(second["id"], "reject")

    assert wf.apply_decision(first["id"], "partial", note="Stock ok, price unchecked")["status"] == "partially_accepted"
    rejected = wf.apply_decision(second["id"], "reject", note="Wrong item")
    assert rejected["status"] == "rejected" and rejected["final_answer"] is None


def test_cannot_decide_twice(fake_ollama):
    item = started()
    wf.apply_decision(item["id"], "approve")
    with pytest.raises(RuntimeError):
        wf.apply_decision(item["id"], "reject", note="changed my mind")


def test_unknown_or_unsafe_ids_are_not_found():
    for bad in ["wf-00000000", "../../etc/passwd", "wf-ZZZZ", ""]:
        assert audit.load_workflow(bad) is None
    with pytest.raises(LookupError):
        wf.apply_decision("../secret", "approve")


def test_history_is_newest_first_and_filters_by_student(fake_ollama):
    a = wf.start_workflow("student-4", "first", EVIDENCE)
    wf.start_workflow("student-2", "other", EVIDENCE)
    a_saved = audit.load_workflow(a["id"])
    a_saved["created_at"] = "2000-01-01T00:00:00+00:00"
    audit.save_workflow(a_saved)

    everything = audit.list_workflows()
    assert len(everything) == 2 and everything[-1]["id"] == a["id"]
    assert [w["student"] for w in audit.list_workflows("student-4")] == ["student-4"]


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

def test_health(client, monkeypatch):
    monkeypatch.setattr(server, "ollama_up", lambda: False)
    data = client.get("/health").get_json()
    assert data["status"] == "ok" and data["port"] == 6004
    assert data["decisions"] == ["approve", "correct", "partial", "reject"]


def test_http_start_then_decide(client, fake_ollama):
    resp = client.post("/workflow/start", json={"student": "student-4", "task": "Check cart", "evidence": EVIDENCE})
    assert resp.status_code == 201
    wf_id = resp.get_json()["id"]

    resp = client.post(f"/workflow/{wf_id}/decision", json={"decision": "approve", "reviewer": "sky"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "approved"

    detail = client.get(f"/workflow/{wf_id}").get_json()
    assert detail["events"][-1]["action"] == "decision_approve"

    history = client.get("/workflows?student=student-4").get_json()
    assert history["count"] == 1 and history["workflows"][0]["human_decision"] == "approve"

    assert client.get(f"/audit?workflow_id={wf_id}").get_json()["count"] == 6


def test_http_errors(client, fake_ollama):
    assert client.post("/workflow/start", json={"task": "no student"}).status_code == 400
    assert client.post("/workflow/start", data="not json").status_code == 400
    assert client.get("/workflow/wf-00000000").status_code == 404
    assert client.post("/workflow/wf-00000000/decision", json={"decision": "approve"}).status_code == 404

    wf_id = client.post("/workflow/start", json={"student": "s", "task": "t", "evidence": EVIDENCE}).get_json()["id"]
    assert client.post(f"/workflow/{wf_id}/decision", json={"decision": "maybe"}).status_code == 400
    client.post(f"/workflow/{wf_id}/decision", json={"decision": "approve"})
    assert client.post(f"/workflow/{wf_id}/decision", json={"decision": "approve"}).status_code == 409


def test_http_start_returns_503_when_ollama_is_down(client, monkeypatch):
    def down(s, u):
        raise agents.AgentError("Ollama call failed")
    monkeypatch.setattr(agents, "ask_ollama", down)
    resp = client.post("/workflow/start", json={"student": "s", "task": "t", "evidence": EVIDENCE})
    assert resp.status_code == 503 and resp.get_json()["status"] == "failed"


# ---------------------------------------------------------------------------
# terminal client
# ---------------------------------------------------------------------------

def test_cli_run_with_decision_flag(fake_ollama, capsys):
    code = cli.main(["run", "--student", "student-4", "--task", "Check cart",
                     "--evidence-json", json.dumps(EVIDENCE), "--decision", "approve", "--reviewer", "sky"])
    out = capsys.readouterr().out
    assert code == 0
    assert "PLANNER" in out and "WORKER" in out and "REVIEWER" in out and "HUMAN  ->  APPROVE" in out


def test_cli_run_asks_human_when_no_flag(fake_ollama, monkeypatch, capsys):
    answers = iter(["maybe", "partial", "Stock ok, price needs a check"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    code = cli.main(["run", "--student", "student-4", "--task", "Check cart",
                     "--evidence-json", json.dumps(EVIDENCE)])
    assert code == 0
    assert "Please type approve" in capsys.readouterr().out
    assert audit.list_workflows()[0]["status"] == "partially_accepted"


def test_cli_list_and_show(fake_ollama, capsys):
    item = started()
    cli.main(["list"])
    cli.main(["show", item["id"]])
    out = capsys.readouterr().out
    assert item["id"] in out and "AUDIT LOG" in out and "awaiting_human_review" in out
