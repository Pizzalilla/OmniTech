import logging

import pytest

import backend.agent
import backend.ai

CLEAN_REVIEW = '{"unsupported_claims": [], "missing_specifications": []}'


class ScriptedModel:
    """Stands in for Ollama, answering summary and review prompts separately."""

    def __init__(self):
        self.summaries: list[str] = []
        self.reviews: list[str] = []
        self.prompts: list[str] = []

    def __call__(self, prompt, **kwargs):
        self.prompts.append(prompt)
        if "Reply with JSON only" in prompt:
            return self.reviews.pop(0) if self.reviews else CLEAN_REVIEW
        return self.summaries.pop(0) if self.summaries else "A tidy paragraph."

    @property
    def summary_prompts(self):
        return [p for p in self.prompts if "Reply with JSON only" not in p]


@pytest.fixture()
def model(monkeypatch):
    scripted = ScriptedModel()
    monkeypatch.setattr(backend.ai, "generate", scripted)
    return scripted


@pytest.fixture()
def first_product(client):
    return client.get("/api/products").get_json()[0]


def review_with(claims=(), missing=()):
    import json

    return json.dumps(
        {
            "unsupported_claims": list(claims),
            "missing_specifications": list(missing),
        }
    )


def test_clean_summary_is_accepted_on_the_first_attempt(client, first_product, model):
    model.summaries = ["Roomy and efficient for a small household."]

    body = client.post(f"/api/products/{first_product['id']}/ai-review").get_json()

    assert body["accepted"] is True
    assert body["attempts"] == 1
    assert body["summary"] == "Roomy and efficient for a small household."
    assert body["warnings"]["rejected_claims"] == []


def test_unsupported_claim_triggers_one_correction(client, first_product, model):
    model.summaries = ["It has smart features.", "It is roomy and efficient."]
    model.reviews = [review_with(claims=["smart features"]), CLEAN_REVIEW]

    body = client.post(f"/api/products/{first_product['id']}/ai-review").get_json()

    assert body["attempts"] == 2
    assert body["accepted"] is True
    assert body["summary"] == "It is roomy and efficient."
    # the retry must tell the model what to drop, or it will repeat itself
    assert "smart features" in model.summary_prompts[1]


def test_summary_is_withheld_when_the_correction_also_fails(
    client, first_product, model
):
    model.summaries = ["It has smart features.", "It still has smart features."]
    model.reviews = [
        review_with(claims=["smart features"]),
        review_with(claims=["smart features"]),
    ]

    body = client.post(f"/api/products/{first_product['id']}/ai-review").get_json()

    assert body["accepted"] is False
    assert body["summary"] is None
    assert body["attempts"] == backend.agent.MAX_ATTEMPTS
    assert "smart features" in body["warnings"]["rejected_claims"]


def test_a_figure_absent_from_the_specs_is_rejected(client, first_product, model):
    model.summaries = ["It holds 9999 litres.", "It is roomy."]

    body = client.post(f"/api/products/{first_product['id']}/ai-review").get_json()

    # the reviewer said nothing, so this has to come from the numeric check
    assert body["attempts"] == 2
    assert body["summary"] == "It is roomy."


def test_missing_specifications_survive_a_correction(client, first_product, model):
    model.summaries = ["It has smart features.", "It is roomy and efficient."]
    model.reviews = [
        review_with(claims=["smart features"], missing=["Noise level"]),
        CLEAN_REVIEW,
    ]

    body = client.post(f"/api/products/{first_product['id']}/ai-review").get_json()

    assert body["attempts"] == 2
    assert body["warnings"]["missing_specifications"] == ["Noise level"]


def test_missing_specifications_are_reported(client, first_product, model):
    model.reviews = [review_with(missing=["Noise level", "Warranty length"])]

    body = client.post(f"/api/products/{first_product['id']}/ai-review").get_json()

    assert body["warnings"]["missing_specifications"] == [
        "Noise level",
        "Warranty length",
    ]


def test_conflicting_specifications_are_reported(client, model):
    category_id = client.get("/api/categories").get_json()[0]["id"]
    product = client.post(
        "/api/products",
        json={
            "name": "Muddled Microwave",
            "brand": "MixUp",
            "category_id": category_id,
            "price": 149.0,
            "stock": 3,
        },
    ).get_json()

    for value in ("800 W", "1000 W"):
        client.post(
            f"/api/products/{product['id']}/specifications",
            json={"spec_name": "Power", "spec_value": value},
        )

    body = client.post(f"/api/products/{product['id']}/ai-review").get_json()

    assert body["warnings"]["conflicting_specs"] == [
        {"spec_name": "power", "values": ["1000 W", "800 W"]}
    ]


def test_review_that_is_not_json_is_treated_as_no_findings(
    client, first_product, model
):
    model.reviews = ["Sure! Everything looks fine to me."]

    body = client.post(f"/api/products/{first_product['id']}/ai-review").get_json()

    assert body["accepted"] is True
    assert body["warnings"]["missing_specifications"] == []


def test_every_stage_is_logged_for_the_terminal(client, first_product, model, caplog):
    with caplog.at_level(logging.INFO, logger="catalog.agent"):
        client.post(f"/api/products/{first_product['id']}/ai-review")

    logged = " ".join(record.getMessage() for record in caplog.records)
    for stage in ("PLAN", "ACT", "OBSERVE", "DONE"):
        assert stage in logged


def test_product_page_offers_the_review_button(client, first_product):
    page = client.get(f"/products/{first_product['id']}").get_data(as_text=True)

    assert f"/products/{first_product['id']}/ai-review" in page
    assert "Generating a summary" in page
    assert "hx-indicator" in page


def test_review_fragment_shows_the_summary(client, first_product, model):
    model.summaries = ["Roomy and efficient."]

    fragment = client.post(
        f"/products/{first_product['id']}/ai-review"
    ).get_data(as_text=True)

    assert "Roomy and efficient." in fragment
    assert "ai-response" in fragment


def test_review_fragment_lists_findings(client, first_product, model):
    model.reviews = [review_with(missing=["Warranty length"])]

    fragment = client.post(
        f"/products/{first_product['id']}/ai-review"
    ).get_data(as_text=True)

    assert "Warranty length" in fragment
    assert "Review findings" in fragment


def test_review_fragment_survives_an_ollama_outage(client, first_product, monkeypatch):
    def refuse(prompt, **kwargs):
        raise backend.ai.AIUnavailable("connection refused")

    monkeypatch.setattr(backend.ai, "generate", refuse)

    response = client.post(f"/products/{first_product['id']}/ai-review")

    # a 200 is deliberate, otherwise htmx would leave the panel empty
    assert response.status_code == 200
    assert "unavailable" in response.get_data(as_text=True)


def test_review_for_unknown_product(client):
    assert client.post("/products/999999/ai-review").status_code == 404
    assert client.post("/api/products/999999/ai-review").status_code == 404


def test_conflict_detection_is_case_insensitive():
    conflicts = backend.agent.find_conflicting_specs(
        [
            {"spec_name": "Power", "spec_value": "800 W"},
            {"spec_name": "power", "spec_value": "1000 W"},
        ]
    )

    assert len(conflicts) == 1


def test_repeated_identical_specs_are_not_a_conflict():
    conflicts = backend.agent.find_conflicting_specs(
        [
            {"spec_name": "Power", "spec_value": "800 W"},
            {"spec_name": "Power", "spec_value": "800 W"},
        ]
    )

    assert conflicts == []


def test_thousands_separators_do_not_read_as_ungrounded():
    assert backend.agent.ungrounded_numbers("Costs $1,299.00", "- Price: $1299.00") == []
