"""POST /api/products and POST /api/products/<id>/ai-summary. CI runs these with AI off."""

import backend.ai


def _category_id(client):
    return client.get("/api/categories").get_json()[0]["id"]


def test_create_product_returns_201_and_persists(client):
    payload = {
        "name": "CI Kettle",
        "brand": "TestCo",
        "category_id": _category_id(client),
        "price": 49.0,
        "stock": 3,
        "description": "Created by the endpoint test",
    }
    response = client.post("/api/products", json=payload)
    assert response.status_code == 201
    created = response.get_json()
    assert created["name"] == "CI Kettle"
    assert created["brand"] == "TestCo"
    stored = client.get(f"/api/products/{created['id']}").get_json()
    assert stored["description"] == "Created by the endpoint test"
    assert stored["price"] == 49.0


def test_create_product_rejects_missing_fields(client):
    response = client.post("/api/products", json={"name": "Only a name"})
    assert response.status_code == 400
    assert "required" in response.get_json()["error"]


def test_create_product_rejects_negative_price(client):
    response = client.post(
        "/api/products",
        json={
            "name": "Broken price",
            "brand": "TestCo",
            "category_id": _category_id(client),
            "price": -1,
            "stock": 1,
        },
    )
    assert response.status_code == 400


def test_ai_summary_unknown_product(client):
    assert client.post("/api/products/99999/ai-summary").status_code == 404


def test_ai_summary_fails_closed_when_ollama_is_down(client, monkeypatch):
    def _down(prompt, json_only=False):
        raise backend.ai.AIUnavailable("could not reach ollama at http://ai-disabled.invalid:11434")

    monkeypatch.setattr(backend.ai, "generate", _down)
    response = client.post("/api/products/1/ai-summary")
    assert response.status_code == 503
    assert response.get_json()["error"] == "ai summary unavailable"
    assert client.get("/api/products/1").status_code == 200
