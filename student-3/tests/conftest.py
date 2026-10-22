"""Shared fixtures for the Student 3 test suite."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "database"))

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "bootstrap.db")

import agent  # noqa: E402
import database  # noqa: E402
import main  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(autouse=True)
def integrations_enabled(monkeypatch):
    # CI runs with RAG/MCP/MULTI_AGENT_ENABLED=false; these tests fake the shared
    # servers, so switch the flags on per test (the *_disabled tests turn them off).
    monkeypatch.setattr(main, "RAG_ENABLED", True)
    monkeypatch.setattr(main, "MCP_ENABLED", True)
    monkeypatch.setattr(main, "MULTI_AGENT_ENABLED", True)


@pytest.fixture
def client(tmp_path):
    # Fresh, isolated database per test so destructive cases cannot bleed.
    database.DB_PATH = str(tmp_path / "test.db")
    database.init_db()
    database.seed_db()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def fake_ollama(monkeypatch):
    """Force agent.act to return a valid, catalog-consistent JSON answer."""
    def _act(prompt):
        return json.dumps({
            "reply": "The Meridian Pro 16 (LAP-001) is the best fit for 4K editing.",
            "recommended_product_ids": ["LAP-001"],
            "summary": "Workstation laptop for heavy 4K timelines.",
        })
    monkeypatch.setattr(agent, "act", _act)
