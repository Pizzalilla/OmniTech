def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_seeded_categories_are_listed(client):
    response = client.get("/api/categories")
    assert response.status_code == 200
    names = [category["name"] for category in response.get_json()]
    assert names == ["Air Conditioners", "Refrigerators", "Washing Machines"]


def test_create_update_and_delete_category(client):
    created = client.post(
        "/api/categories",
        json={"name": "Dishwashers", "description": "Kitchen cleaning"},
    )
    assert created.status_code == 201
    category_id = created.get_json()["id"]

    updated = client.put(
        f"/api/categories/{category_id}",
        json={"name": "Dishwashers", "description": "Updated blurb"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["description"] == "Updated blurb"

    assert client.delete(f"/api/categories/{category_id}").status_code == 204
    assert client.get(f"/api/categories/{category_id}").status_code == 404


def test_create_category_requires_name(client):
    response = client.post("/api/categories", json={"description": "no name"})
    assert response.status_code == 400


def test_duplicate_category_name_is_rejected(client):
    response = client.post("/api/categories", json={"name": "Refrigerators"})
    assert response.status_code == 409


def test_category_in_use_cannot_be_deleted(client):
    response = client.delete("/api/categories/1")
    assert response.status_code == 409
