"""
Release 1 tests for the grounded AI helper (backend/agent.py).

No Ollama or RAG server needed: the LLM and RAG calls are replaced with fakes,
and every test uses its own temporary orders.db, so this file runs in CI.
"""

import copy
import os
import sqlite3
import sys

import pytest
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
sys.path.insert(0, os.path.join(HERE, "..", "database"))

import database as db  # noqa: E402
import init_db  # noqa: E402
import agent  # noqa: E402
import main  # noqa: E402

KNOWLEDGE = [{
    "source": "appliance-installation-and-cart.md",
    "heading": "Running Kitchen Appliances Together",
    "text": "Heating appliances each draw 1000W or more. Plug each into its own power point.",
}]


# FIXTURE: fresh temp database + demo cart + fake RAG for every test
@pytest.fixture
def setup(tmp_path, monkeypatch):
    db_file = str(tmp_path / "orders.db")
    monkeypatch.setattr(db, "DB_FILE", db_file)
    monkeypatch.setattr(init_db, "DB_FILE", db_file)
    monkeypatch.setattr(db, "_specs_ready", False)
    monkeypatch.setattr(agent, "retrieve_knowledge", lambda query, limit=3: (KNOWLEDGE, "ok", "high"))
    monkeypatch.setattr(agent, "MCP_ENABLED", False)   # MCP paths are tested in test_mcp.py
    main.CUSTOMER_CART["items"] = copy.deepcopy(main.DEMO_CART_ITEMS)
    main.app.testing = True
    return main.app.test_client()


# FAKE LLM: returns the given answers in order and records each prompt
def fake_llm(monkeypatch, answers):
    prompts = []

    def _ask(prompt):
        prompts.append(prompt)
        return answers[min(len(prompts), len(answers)) - 1]
    monkeypatch.setattr(agent, "ask_llm", _ask)
    return prompts


# --- PLAN: facts + checks ---

def test_cart_facts_come_from_database(setup):
    facts = agent.get_cart_facts(main.CUSTOMER_CART["items"])
    assert all(f["has_specs"] for f in facts)
    fridge = facts[0]
    assert fridge["product_name"] == "Samsung Fridge 500L"
    assert fridge["width_mm"] == 700 and fridge["weight_kg"] == 82


def test_safety_checks_flag_power_weight_and_stock(setup):
    checks = agent.run_cart_checks(agent.get_cart_facts(main.CUSTOMER_CART["items"]))
    text = " ".join(c["text"] for c in checks)
    assert "5200W" in text and "10A power point" in text     # induction + microwave + air fryer
    assert "82 kg - two-person delivery" in text
    assert "Microwave Oven 1000W: out of stock" in text


def test_hardwired_cooktop_is_flagged(setup):
    items = [{"product_id": 505, "product_name": "Built-in Induction Cooktop 4-Zone", "category": "Kitchen",
              "unit_price": 1299.5, "quantity": 1, "in_stock": True}]
    checks = agent.run_cart_checks(agent.get_cart_facts(items))
    assert any("licensed electrician" in c["text"] for c in checks)


def test_unknown_product_has_no_specs(setup):
    items = [{"product_id": 9999, "product_name": "Mystery Box", "category": "Misc",
              "unit_price": 1, "quantity": 1, "in_stock": True}]
    facts = agent.get_cart_facts(items)
    assert facts[0]["has_specs"] is False
    assert "no specs on file" in agent.run_cart_checks(facts)[0]["text"]


def test_old_database_without_specs_table_is_upgraded(setup, monkeypatch):
    init_db.init_database()
    conn = sqlite3.connect(db.DB_FILE)
    conn.execute("DROP TABLE product_specs")
    conn.commit()
    conn.close()
    monkeypatch.setattr(db, "_specs_ready", False)
    assert 511 in db.get_product_specs([511])


# --- OBSERVE: number checking ---

def test_verifier_accepts_facts_and_rejects_made_up_numbers(setup):
    facts = agent.get_cart_facts(main.CUSTOMER_CART["items"])
    fact_text = "\n".join(agent.describe_product(f) for f in facts)
    allowed = agent.allowed_numbers(fact_text, "", [f["power_w"] for f in facts])

    good = "The fridge is 70cm wide, 1.78m tall, 82 kg, 4-star, 390 kWh/year. Cooktop + microwave = 3500W (14.6A) on 240V."
    assert agent.find_unsupported(good, allowed) == []

    bad = "The fridge is 95cm wide, weighs 60kg and is 5-star."
    assert agent.find_unsupported(bad, allowed) == ["95cm", "60kg", "5-star"]


def test_extract_numbers_handles_commas_and_units():
    found = agent.extract_numbers("Uses 2,000W and 2kW, needs 5 cm, 10 amps, 20 litres. Takes 3 minutes.")
    assert [(v, u) for v, u, _ in found] == [(2000, "W"), (2000, "W"), (50, "mm"), (10, "A"), (20, "L")]


# --- ACT / OBSERVE / ADAPT: the full loop ---

def test_grounded_answer_is_verified_first_time(setup, monkeypatch):
    prompts = fake_llm(monkeypatch, ["The Samsung fridge needs 50mm at the back and 20mm at the sides."])
    result = agent.run_cart_agent("How much space does the fridge need?", main.CUSTOMER_CART["items"])
    assert result["status"] == "verified" and result["attempts"] == 1
    assert "700mm W x 1780mm H" in prompts[0]           # real specs went into the prompt
    assert "Running Kitchen Appliances Together" in prompts[0]   # RAG knowledge went into the prompt


def test_agent_retries_once_with_feedback(setup, monkeypatch):
    prompts = fake_llm(monkeypatch, ["It needs 15cm at the back.", "It needs 5cm at the back."])
    result = agent.run_cart_agent("Fridge clearance?", main.CUSTOMER_CART["items"])
    assert result["status"] == "verified" and result["attempts"] == 2
    assert "15cm" in prompts[1] and "NOT in the facts" in prompts[1]


def test_agent_falls_back_to_facts_when_ai_keeps_guessing(setup, monkeypatch):
    fake_llm(monkeypatch, ["The fridge weighs 999kg."])
    result = agent.run_cart_agent("How heavy is it?", main.CUSTOMER_CART["items"])
    assert result["status"] == "fallback"
    assert result["unsupported"] == ["999kg"]
    assert "Samsung Fridge 500L" in result["answer"] and "999" not in result["answer"]


def test_agent_offline_when_ollama_down(setup, monkeypatch):
    def _down(prompt):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(agent, "ask_llm", _down)
    result = agent.run_cart_agent("", main.CUSTOMER_CART["items"])
    assert result["status"] == "offline"
    assert "Samsung Fridge 500L" in result["answer"]


# --- RAG client ---

class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


def test_rag_retrieve_endpoint_used(monkeypatch):
    monkeypatch.setattr(agent, "RAG_ENABLED", True)
    calls = []

    def _post(url, json, timeout):
        calls.append(url)
        return FakeResponse(200, {"chunks": KNOWLEDGE, "confidence": "high"})
    monkeypatch.setattr(agent.requests, "post", _post)
    chunks, status, confidence = agent.retrieve_knowledge("power point")
    assert status == "ok" and chunks == KNOWLEDGE and confidence == "high"
    assert calls[0].endswith("/rag/retrieve")


def test_rag_falls_back_to_query_endpoint_on_older_server(monkeypatch):
    monkeypatch.setattr(agent, "RAG_ENABLED", True)
    def _post(url, json, timeout):
        if url.endswith("/rag/retrieve"):
            return FakeResponse(404, {})
        return FakeResponse(200, {"answer": "x", "citations": [
            {"source": "a.md", "section": "Sec", "snippet": "text"}]})
    monkeypatch.setattr(agent.requests, "post", _post)
    chunks, status, _ = agent.retrieve_knowledge("power point")
    assert status == "ok" and chunks == [{"source": "a.md", "heading": "Sec", "text": "text"}]


def test_rag_offline_returns_empty(monkeypatch):
    monkeypatch.setattr(agent, "RAG_ENABLED", True)
    def _post(url, json, timeout):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(agent.requests, "post", _post)
    assert agent.retrieve_knowledge("power point") == ([], "offline", None)


def test_rag_insufficient_context(monkeypatch):
    monkeypatch.setattr(agent, "RAG_ENABLED", True)
    def _post(url, json, timeout):
        return FakeResponse(200, {"chunks": [], "confidence": "low", "insufficient_context": True})
    monkeypatch.setattr(agent.requests, "post", _post)
    assert agent.retrieve_knowledge("who won the football") == ([], "insufficient", None)


def test_rag_disabled_makes_no_call(monkeypatch):
    def _post(url, json, timeout):
        raise AssertionError("RAG must not be called when RAG_ENABLED=false")
    monkeypatch.setattr(agent.requests, "post", _post)
    monkeypatch.setattr(agent, "RAG_ENABLED", False)
    assert agent.retrieve_knowledge("power point") == ([], "disabled", None)


# --- ROUTE: HTML + JSON ---

def test_route_shows_answer_sources_checks_and_trace(setup, monkeypatch):
    fake_llm(monkeypatch, ["Use separate power points for the cooktop and air fryer. <script>x</script>"])
    res = setup.post("/api/orders/ai-validate-cart", data={"question": "Can I share a power point?"})
    html = res.get_data(as_text=True)
    assert res.status_code == 200
    assert "ai-alert-box success" in html
    assert "appliance-installation-and-cart.md › Running Kitchen Appliances Together" in html
    assert "Cart database (4 products)" in html
    assert "rag-badge high" in html and "RAG confidence: high" in html
    assert "How the agent worked" in html and "Observe:" in html
    assert "<script>" not in html and "&lt;script&gt;" in html   # AI text is escaped


def test_route_offline_banner(setup, monkeypatch):
    def _down(prompt):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(agent, "ask_llm", _down)
    html = setup.post("/api/orders/ai-validate-cart").get_data(as_text=True)
    assert "ai-alert-box error" in html and "AI Helper Offline" in html


def test_route_json_for_other_services(setup, monkeypatch):
    fake_llm(monkeypatch, ["The air fryer draws 1700W."])
    res = setup.post("/api/orders/ai-validate-cart", json={"question": "Air fryer power?"})
    body = res.get_json()
    assert body["status"] == "verified"
    assert body["knowledge"][0]["source"] == "appliance-installation-and-cart.md"


def test_route_shows_insufficient_context_message(setup, monkeypatch):
    monkeypatch.setattr(agent, "retrieve_knowledge", lambda query, limit=3: ([], "insufficient", None))
    fake_llm(monkeypatch, ["I don't have that information."])
    html = setup.post("/api/orders/ai-validate-cart", data={"question": "Who won the football?"}).get_data(as_text=True)
    assert "don't have enough information in the store knowledge" in html
    assert "not enough information in the store knowledge" in html   # also in the agent trace


# OLLAMA ADDRESS: Windows-style OLLAMA_HOST values still give a callable URL
def test_ollama_url_handles_windows_setting():
    assert agent.ollama_url("0.0.0.0:11434") == "http://127.0.0.1:11434"
    assert agent.ollama_url("http://ollama-service:11434/") == "http://ollama-service:11434"
    assert agent.ollama_url(None) == "http://127.0.0.1:11434"


# CLAIM CHECK: claims with no new number are still checked against the facts
def test_claim_check_catches_hardwiring_and_rating_claims(setup):
    facts = agent.get_cart_facts(main.CUSTOMER_CART["items"])          # demo cart: all 10A plug-in
    assert agent.find_unsupported_claims("The cooktop needs a 32A hardwired circuit.", facts)
    assert agent.find_unsupported_claims("Get a licensed electrician to install it.", facts)
    assert agent.find_unsupported_claims("4-star is the highest rating available in Australia.", facts)
    assert agent.find_unsupported_claims("Use separate 10A power points.", facts) == []

    built_in = [{"product_id": 505, "product_name": "Built-in Induction Cooktop 4-Zone", "category": "Kitchen",
                 "unit_price": 1299.5, "quantity": 1, "in_stock": True}]
    hardwired_facts = agent.get_cart_facts(built_in)
    assert agent.find_unsupported_claims("It must be hardwired by a licensed electrician.", hardwired_facts) == []


def test_agent_retries_when_answer_makes_a_hardwiring_claim(setup, monkeypatch):
    prompts = fake_llm(monkeypatch, ["The cooktop needs a 32A hardwired circuit.",
                                     "Plug the cooktop and air fryer into separate 10A power points."])
    result = agent.run_cart_agent("", main.CUSTOMER_CART["items"])
    assert result["status"] == "verified" and result["attempts"] == 2
    assert "hardwiring" in prompts[1]
    assert "no hardwiring or electrician needed" in prompts[0]      # plug-in fact is spelled out


def test_markdown_bold_is_rendered_but_html_still_escaped(setup, monkeypatch):
    fake_llm(monkeypatch, ["**Power:** use separate 10A power points <b>x</b>"])
    html = setup.post("/api/orders/ai-validate-cart", data={"question": "Power?"}).get_data(as_text=True)
    assert "<strong>Power:</strong>" in html and "**" not in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html
