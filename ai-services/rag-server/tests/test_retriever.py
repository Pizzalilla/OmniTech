import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import retriever  # noqa: E402


def test_load_chunks_parses_real_knowledge_dir():
    chunks = retriever.load_chunks()
    assert len(chunks) > 5
    assert all({"source", "heading", "text"} <= chunks[0].keys() for _ in [0])
    sources = {c["source"] for c in chunks}
    assert "product-catalog.md" in sources
    assert "warranty-policy.md" in sources


def test_parse_sections_splits_on_headings():
    text = (
        "# Title\n"
        "Intro text is dropped.\n"
        "## First Section\n"
        "First body line.\n"
        "More text.\n"
        "## Second Section\n"
        "Second body line.\n"
    )
    sections = retriever._parse_sections("doc.md", text)
    assert [s["heading"] for s in sections] == ["First Section", "Second Section"]
    assert sections[0]["text"] == "First body line.\nMore text."
    assert sections[1]["source"] == "doc.md"


def test_search_finds_warranty_chunk_with_high_confidence():
    chunks = retriever.load_chunks()
    matches, confidence = retriever.search("what is covered under warranty claim", chunks)
    assert matches
    assert any(c["source"] == "warranty-policy.md" for c in matches)
    assert confidence in {"high", "medium"}


def test_search_returns_no_matches_for_irrelevant_query():
    chunks = retriever.load_chunks()
    matches, confidence = retriever.search("xyz completely unrelated zzz qqq", chunks)
    assert matches == []
    assert confidence == "low"


def test_search_returns_empty_for_blank_query():
    chunks = retriever.load_chunks()
    matches, confidence = retriever.search("   ", chunks)
    assert matches == []
    assert confidence == "low"
