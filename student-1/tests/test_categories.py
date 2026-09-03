def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_seed_meets_minimum_record_count(client):
    categories = client.get("/api/categories").get_json()
    assert len(categories) >= 10


def test_categories_are_listed_alphabetically(client):
    names = [category["name"] for category in client.get("/api/categories").get_json()]
    assert names == sorted(names)


def test_create_update_and_delete_category(client):
    created = client.post(
        "/api/categories",
        json={"name": "Garment Steamers", "description": "Handheld steaming"},
    )
    assert created.status_code == 201
    category_id = created.get_json()["id"]

    updated = client.put(
        f"/api/categories/{category_id}",
        json={"name": "Garment Steamers", "description": "Updated blurb"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["description"] == "Updated blurb"

    assert client.delete(f"/api/categories/{category_id}").status_code == 204
    assert client.get(f"/api/categories/{category_id}").status_code == 404


def test_create_category_requires_name(client):
    response = client.post("/api/categories", json={"description": "no name"})
    assert response.status_code == 400


def test_duplicate_category_name_is_rejected(client):
    existing = client.get("/api/categories").get_json()[0]["name"]
    response = client.post("/api/categories", json={"name": existing})
    assert response.status_code == 409


def test_category_in_use_cannot_be_deleted(client):
    in_use = client.get("/api/products").get_json()[0]["category_id"]
    response = client.delete(f"/api/categories/{in_use}")
    assert response.status_code == 409
