"""
Retrieval layer for the shared RAG server.

Documents live as markdown files under knowledge/. Each file is split into
chunks on its "## " section headings, so every chunk can be cited back to a
specific section rather than a whole file. Scoring is deterministic keyword
overlap - the same approach student-3's catalog.search() uses - so retrieval
needs no embedding model or extra dependencies beyond the standard library.
"""

import os

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")

_STOPWORDS = {
    "the", "for", "and", "with", "that", "this", "you", "your", "need", "needs",
    "want", "wants", "best", "good", "great", "under", "over", "about", "any",
    "can", "get", "got", "have", "has", "would", "should", "could", "please",
    "what", "which", "who", "how", "does", "do", "is", "are", "was", "were",
    "when", "where", "will", "our", "their", "from", "into", "than", "them",
}


def load_chunks(knowledge_dir=KNOWLEDGE_DIR):
    """Parse every knowledge/*.md file into a flat list of chunk dicts:
    {"source": filename, "heading": section title, "text": section body}."""
    chunks = []
    for filename in sorted(os.listdir(knowledge_dir)):
        if not filename.endswith(".md"):
            continue
        path = os.path.join(knowledge_dir, filename)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        chunks.extend(_parse_sections(filename, text))
    return chunks


def _parse_sections(filename, text):
    heading = None
    body_lines = []
    sections = []

    def flush():
        if heading and body_lines:
            body = "\n".join(body_lines).strip()
            if body:
                sections.append({"source": filename, "heading": heading, "text": body})

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            heading = line[3:].strip()
            body_lines = []
        elif line.startswith("# "):
            continue  # document title, not a citable section
        elif heading is not None:
            body_lines.append(line)
    flush()
    return sections


def _tokenize(text):
    raw = [t.strip(".,!?;:$()'\"") for t in (text or "").lower().split()]
    return {t for t in raw if len(t) > 2 and t not in _STOPWORDS}


def search(query, chunks, limit=4, min_score=2):
    """Rank chunks against a free-text query.

    Returns (matches, confidence). `matches` is empty when nothing clears
    `min_score` - callers should treat that as insufficient context rather
    than generating an answer. `confidence` is derived from the top match's
    score: "high" (>=8), "medium" (>=4), or "low" otherwise.
    """
    tokens = _tokenize(query)
    if not tokens:
        return [], "low"

    scored = []
    for chunk in chunks:
        heading_l = chunk["heading"].lower()
        text_l = chunk["text"].lower()
        score = 3 * sum(1 for t in tokens if t in heading_l)
        score += sum(1 for t in tokens if t in text_l)
        if score >= min_score:
            scored.append((score, chunk))

    if not scored:
        return [], "low"

    scored.sort(key=lambda pair: pair[0], reverse=True)
    top_score = scored[0][0]
    matches = [chunk for _, chunk in scored[:limit]]

    if top_score >= 8:
        confidence = "high"
    elif top_score >= 4:
        confidence = "medium"
    else:
        confidence = "low"
    return matches, confidence
