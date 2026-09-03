import pytest

import backend.ai

STUB_SUMMARY = "A dependable everyday choice for a small household."


@pytest.fixture()
def sent_prompts(monkeypatch):
    prompts = []

    def stub_generate(prompt):
        prompts.append(prompt)
        return STUB_SUMMARY

    monkeypatch.setattr(backend.ai, "generate", stub_generate)
    return prompts


@pytest.fixture()
def first_product(client):
    return client.get("/api/products").get_json()[0]


def test_summary_returns_generated_paragraph(client, first_product, sent_prompts):
    response = client.post(f"/api/products/{first_product['id']}/ai-summary")

    assert response.status_code == 200
    body = response.get_json()
    assert body["summary"] == STUB_SUMMARY
    assert body["product_id"] == first_product["id"]
    assert body["model"]


def test_summary_prompt_carries_the_stored_specifications(
    client, first_product, sent_prompts
):
    specifications = client.get(
        f"/api/products/{first_product['id']}/specifications"
    ).get_json()

    client.post(f"/api/products/{first_product['id']}/ai-summary")

    prompt = sent_prompts[0]
    assert first_product["name"] in prompt
    assert first_product["brand"] in prompt
    for spec in specifications:
        assert spec["spec_name"] in prompt
        assert spec["spec_value"] in prompt


def test_summary_prompt_forbids_invented_specifications(
    client, first_product, sent_prompts
):
    client.post(f"/api/products/{first_product['id']}/ai-summary")

    assert "Never invent" in sent_prompts[0]


def test_summary_for_product_without_specifications(client, sent_prompts):
    category_id = client.get("/api/categories").get_json()[0]["id"]
    created = client.post(
        "/api/products",
        json={
            "name": "Spec Free Kettle",
            "brand": "PlainCo",
            "category_id": category_id,
            "price": 39.99,
            "stock": 4,
        },
    ).get_json()

    response = client.post(f"/api/products/{created['id']}/ai-summary")

    assert response.status_code == 200
    assert "none recorded" in sent_prompts[0]


def test_summary_for_unknown_product(client):
    assert client.post("/api/products/999999/ai-summary").status_code == 404


def test_summary_reports_when_ollama_is_down(client, first_product, monkeypatch):
    def refuse(prompt):
        raise backend.ai.AIUnavailable("connection refused")

    monkeypatch.setattr(backend.ai, "generate", refuse)

    response = client.post(f"/api/products/{first_product['id']}/ai-summary")

    assert response.status_code == 503
    assert response.get_json()["error"] == "ai summary unavailable"
