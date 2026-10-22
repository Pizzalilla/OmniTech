"""
Shared test setup for student-4.

CI runs the service with AI_ENABLED=false (same as the cloud), but the unit
tests fake Ollama, MCP, RAG and the Multi-Agent server themselves, so every
test starts with the AI switch on. Tests that check the AI-off behaviour
switch it off again themselves.
"""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
sys.path.insert(0, os.path.join(HERE, "..", "database"))

import agent  # noqa: E402


@pytest.fixture(autouse=True)
def ai_switched_on(monkeypatch):
    monkeypatch.setattr(agent, "AI_ENABLED", True)
