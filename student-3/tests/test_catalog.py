import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import catalog  # noqa: E402

REQUIRED_KEYS = {"id", "name", "category", "brand", "price", "specs", "description"}


def test_every_product_is_complete():
    for p in catalog.all_products():
        assert REQUIRED_KEYS <= set(p), p
        assert isinstance(p["price"], int)


def test_ids_are_unique():
    ids = [p["id"] for p in catalog.all_products()]
    assert len(ids) == len(set(ids))


def test_get_many_drops_unknown_and_dedupes():
    got = catalog.get_many(["LAP-001", "LAP-001", "NOPE"])
    assert [p["id"] for p in got] == ["LAP-001"]


def test_search_ranks_relevant_products_first():
    hits = catalog.search("wireless noise cancelling headphones for commuting")
    assert hits[0]["category"] == "Headphones"


def test_search_never_returns_empty():
    assert catalog.search("zzzzz nonsense query") != []


def test_context_block_lists_ids_and_prices():
    block = catalog.context_block()
    assert "LAP-001" in block and "$2399" in block
