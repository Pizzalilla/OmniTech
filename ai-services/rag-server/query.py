"""
Command-line client for manually validating the RAG server from a terminal.

Usage:
    python query.py "What is your return policy?"

Prints the raw JSON response from POST /rag/query - useful for capturing
terminal validation evidence for the Release 1 report.
"""

import json
import os
import sys

import requests

RAG_HOST = os.getenv("RAG_HOST", "http://localhost:6002")


def main():
    if len(sys.argv) < 2:
        print('usage: python query.py "<question>"')
        sys.exit(1)
    question = " ".join(sys.argv[1:])
    resp = requests.post(f"{RAG_HOST}/rag/query", json={"query": question}, timeout=125)
    resp.raise_for_status()
    print(json.dumps(resp.json(), indent=2))


if __name__ == "__main__":
    main()
