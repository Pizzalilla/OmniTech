"""
Client for the shared Release 1 RAG server.

Calls the shared, non-containerised RAG server used by every OmniTech feature
(see ai-services/rag-server) - the same connection pattern as OLLAMA_HOST for
the local AI-Mode. All retrieval and generation logic lives in that server;
this module only speaks HTTP to it.
"""

import os

import requests

RAG_HOST = os.getenv("RAG_HOST", "http://localhost:6002")
RAG_TIMEOUT = int(os.getenv("RAG_TIMEOUT", "125"))


def ask(query):
    """POST a question to the shared RAG server.

    Returns the server's JSON response unchanged - either
    {"answer", "citations", "confidence"} or
    {"insufficient_context": True, "message"}.

    Raises requests.RequestException if the RAG server cannot be reached;
    callers are expected to handle that (e.g. to show an "offline" state).
    """
    resp = requests.post(
        f"{RAG_HOST}/rag/query", json={"query": query}, timeout=RAG_TIMEOUT
    )
    resp.raise_for_status()
    return resp.json()