import json
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import agent  # noqa: E402
import catalog  # noqa: E402

VALID = catalog.VALID_IDS


def test_observe_accepts_well_formed_answer():
    raw = json.dumps({
        "reply": "Try the Meridian Air 13 (LAP-002).",
        "recommended_product_ids": ["LAP-002"],
        "summary": "Light everyday laptop.",
    })
    ok, data, issues = agent.observe(raw, VALID)
    assert ok is True
    assert issues == []
    assert data["recommended_product_ids"] == ["LAP-002"]


def test_observe_rejects_non_json():
    ok, data, issues = agent.observe("sorry, here are some ideas...", VALID)
    assert ok is False
    assert data is None
    assert issues


def test_observe_flags_hallucinated_ids():
    raw = json.dumps({
        "reply": "Buy the UltraPhone 9000.",
        "recommended_product_ids": ["FAKE-001"],
        "summary": "n/a",
    })
    ok, data, issues = agent.observe(raw, VALID)
    assert ok is False
    assert any("not in the catalog" in i for i in issues)
    assert data["recommended_product_ids"] == []  # scrubbed


def test_observe_salvages_ids_named_only_in_reply():
    """Naming a catalog id in the prose counts as recommending it, even if the
    list field is empty (small models often do this)."""
    raw = json.dumps({
        "reply": "LAP-001 is ideal for you.",
        "recommended_product_ids": [],
        "summary": "x",
    })
    ok, data, issues = agent.observe(raw, VALID)
    assert ok is True
    assert data["recommended_product_ids"] == ["LAP-001"]


def test_observe_ignores_literal_ID_placeholder():
    """A model that copies the ["ID"] placeholder from the prompt still passes
    when it named a real id in the reply."""
    raw = json.dumps({
        "reply": "The Meridian Air 13 (LAP-002) is a great light laptop.",
        "recommended_product_ids": ["ID"],
        "summary": "light laptop",
    })
    ok, data, issues = agent.observe(raw, VALID)
    assert ok is True
    assert data["recommended_product_ids"] == ["LAP-002"]


def test_run_consultation_uses_fallback_when_ollama_down(monkeypatch):
    def _boom(prompt):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(agent, "act", _boom)

    result = agent.run_consultation("I need noise cancelling headphones")
    assert result["reply"]
    assert result["meta"]["used_fallback"] is True
    assert all(pid in VALID for pid in result["recommended_product_ids"])


def test_run_consultation_adapts_after_bad_first_answer(monkeypatch):
    calls = {"n": 0}

    def _act(prompt):
        calls["n"] += 1
        if calls["n"] == 1:
            return json.dumps({
                "reply": "Get the MysteryBox 5000.",
                "recommended_product_ids": ["FAKE-999"],
                "summary": "bad",
            })
        return json.dumps({
            "reply": "The EchoStudio Over-Ear (AUD-002) blocks noise well.",
            "recommended_product_ids": ["AUD-002"],
            "summary": "ANC over-ear headphones.",
        })

    monkeypatch.setattr(agent, "act", _act)
    result = agent.run_consultation("headphones to block train noise")
    assert calls["n"] == 2                       # one corrective re-prompt
    assert result["meta"]["reprompts"] == 1
    assert result["meta"]["used_fallback"] is False
    assert result["recommended_product_ids"] == ["AUD-002"]
