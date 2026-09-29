"""
Shared local RAG server for the OmniTech Release 1 group project.

One instance of this server runs locally (not in Docker) and is called by
every student feature's backend/API, the same way OLLAMA_HOST is already used
for the local AI-Mode. It retrieves relevant context from knowledge/*.md and
uses the local Ollama model to produce a grounded answer with citations and a
confidence category - or reports insufficient context instead of guessing.

Endpoints:
    GET  /health        liveness check
    POST /rag/query      body {"query": str} -> grounded answer (see README.md)
    POST /rag/retrieve   body {"query": str, "limit": int} -> matching chunks only

Run directly (not via Docker):
    python server.py
"""

import json
import logging
import os
import re

import requests
from flask import Flask, jsonify, request

import retriever

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
RAG_PORT = int(os.getenv("RAG_PORT", "6002"))
TOP_K = int(os.getenv("RAG_TOP_K", "4"))

log = logging.getLogger("rag-server")
if not log.handlers:
    log.setLevel(logging.INFO)
    log.addHandler(logging.StreamHandler())
for _h in log.handlers:
    _h.setFormatter(logging.Formatter("%(asctime)s  rag  %(message)s"))

app = Flask(__name__)
_CHUNKS = retriever.load_chunks()

SYSTEM_INSTRUCTIONS = (
    "You are the OmniTech Marketplace assistant. Answer the customer's "
    "question using ONLY the SOURCE EXCERPTS below - do not use outside "
    "knowledge and do not guess. If the excerpts do not answer the question, "
    "say so plainly instead of making something up.\n"
    "Answer with ONE JSON object and nothing else: "
    '{"answer": "<your answer, grounded in the excerpts>"}'
)


def _build_prompt(query, chunks):
    lines = [SYSTEM_INSTRUCTIONS, "", "SOURCE EXCERPTS:"]
    for i, chunk in enumerate(chunks, 1):
        lines.append(f"[{i}] ({chunk['source']} - {chunk['heading']}) {chunk['text']}")
    lines += ["", f"Customer question: {query}"]
    return "\n".join(lines)


def _extract_answer(raw, chunks):
    raw = (raw or "").strip()
    data = None
    try:
        data = json.loads(raw)
    except ValueError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except ValueError:
                data = None
    if isinstance(data, dict) and str(data.get("answer", "")).strip():
        return str(data["answer"]).strip()
    return _excerpt_answer(chunks)


def _excerpt_answer(chunks):
    """Deterministic answer built straight from the top excerpt, used when
    Ollama is unreachable or returns something unusable."""
    top = chunks[0]
    return f"Based on {top['source']} ({top['heading']}): {top['text']}"


def generate(query, chunks):
    """POST the grounded prompt to Ollama and return the answer text.

    Raises requests.RequestException if Ollama cannot be reached.
    """
    resp = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": _build_prompt(query, chunks),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        },
        timeout=OLLAMA_TIMEOUT,
    )
    resp.raise_for_status()
    raw = resp.json().get("response", "")
    return _extract_answer(raw, chunks)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "chunks_loaded": len(_CHUNKS)})


@app.route("/rag/query", methods=["POST"])
def query():
    body = request.get_json(silent=True) or {}
    q = str(body.get("query", "")).strip()
    if not q:
        return jsonify({"error": "query is required"}), 400

    log.info("QUERY  %r", q[:120])
    matches, confidence = retriever.search(q, _CHUNKS, limit=TOP_K)
    if not matches:
        log.info("RETRIEVE no relevant context found")
        return jsonify({
            "insufficient_context": True,
            "message": "I don't have enough information to answer that yet.",
        })

    log.info("RETRIEVE %d chunk(s) confidence=%s sources=%s",
              len(matches), confidence, [c["source"] for c in matches])

    try:
        answer = generate(q, matches)
    except requests.RequestException as exc:
        log.warning("GENERATE ollama unreachable (%s) -> excerpt fallback", exc)
        answer = _excerpt_answer(matches)
        confidence = "low"

    citations = [
        {"source": c["source"], "section": c["heading"], "snippet": c["text"][:220]}
        for c in matches
    ]
    return jsonify({"answer": answer, "citations": citations, "confidence": confidence})


@app.route("/rag/retrieve", methods=["POST"])
def retrieve():
    """Retrieval only (no Ollama call) - for feature backends that run their
    own grounded prompt and just need the matching knowledge sections."""
    body = request.get_json(silent=True) or {}
    q = str(body.get("query", "")).strip()
    if not q:
        return jsonify({"error": "query is required"}), 400
    try:
        limit = max(1, min(int(body.get("limit", TOP_K)), 10))
    except (TypeError, ValueError):
        limit = TOP_K

    matches, confidence = retriever.search(q, _CHUNKS, limit=limit)
    log.info("RETRIEVE-ONLY %d chunk(s) confidence=%s for %r", len(matches), confidence, q[:80])
    return jsonify({
        "chunks": [{"source": c["source"], "heading": c["heading"], "text": c["text"]} for c in matches],
        "confidence": confidence,
        "insufficient_context": not matches,
    })


if __name__ == "__main__":
    log.info("RAG server starting on port %d with %d knowledge chunk(s)",
              RAG_PORT, len(_CHUNKS))
    app.run(host="0.0.0.0", port=RAG_PORT)
