import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import agent

def test_observe_valid_tags():
    raw = json.dumps({
        "recommended_tags": ["apple-ecosystem", "4k-video-editing"],
        "reasoning": "User needs high end video setup."
    })
    ok, data, issues = agent.observe(raw)
    assert ok is True
    assert "apple-ecosystem" in data["recommended_tags"]

def test_observe_rejects_hallucinated_tags():
    raw = json.dumps({
        "recommended_tags": ["invalid-hallucinated-tag"],
        "reasoning": "none"
    })
    ok, data, issues = agent.observe(raw)
    assert ok is False

def test_fallback_plan():
    ctx = {"preferences_text": "Uses apple hardware and 4k editing"}
    res = agent.fallback_plan(ctx)
    assert "apple-ecosystem" in res["recommended_tags"]