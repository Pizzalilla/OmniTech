"""
Talks to the shared local RAG server.
"""

import os

import requests

RAG_HOST = os.getenv("RAG_HOST", "http://localhost:6002")
RAG_TIMEOUT = int(os.getenv("RAG_TIMEOUT", "125"))


def ask(query):
    resp = requests.post(
        f"{RAG_HOST}/rag/query", json={"query": query}, timeout=RAG_TIMEOUT
    )
    resp.raise_for_status()
    return resp.json()


def retrieve(query, limit=2):
    # chunks only, no Ollama call
    resp = requests.post(
        f"{RAG_HOST}/rag/retrieve",
        json={"query": query, "limit": limit},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("chunks", [])
