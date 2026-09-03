def test_every_seeded_product_has_specifications(client):
    products = client.get("/api/products").get_json()
    for product in products:
        specs = client.get(f"/api/products/{product['id']}/specifications").get_json()
        assert specs, f"{product['name']} has no specifications"


def test_specifications_are_listed_alphabetically(client):
    specs = client.get("/api/products/1/specifications").get_json()
    names = [spec["spec_name"] for spec in specs]
    assert names == sorted(names)


def test_create_update_and_delete_specification(client):
    created = client.post(
        "/api/products/1/specifications",
        json={"spec_name": "Warranty", "spec_value": "5 years"},
    )
    assert created.status_code == 201
    spec_id = created.get_json()["id"]

    updated = client.put(
        f"/api/products/1/specifications/{spec_id}",
        json={"spec_name": "Warranty", "spec_value": "3 years"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["spec_value"] == "3 years"

    assert client.delete(f"/api/products/1/specifications/{spec_id}").status_code == 204
    assert client.get(f"/api/products/1/specifications/{spec_id}").status_code == 404


def test_specification_requires_name_and_value(client):
    response = client.post(
        "/api/products/1/specifications",
        json={"spec_name": "", "spec_value": "12000 BTU"},
    )
    assert response.status_code == 400


def test_specifications_for_unknown_product(client):
    response = client.get("/api/products/999/specifications")
    assert response.status_code == 404


def test_specification_cannot_be_reached_through_another_product(client):
    spec_id = client.get("/api/products/1/specifications").get_json()[0]["id"]
    response = client.get(f"/api/products/2/specifications/{spec_id}")
    assert response.status_code == 404


def test_deleting_product_removes_its_specifications(client):
    category_id = client.get("/api/categories").get_json()[0]["id"]
    created = client.post(
        "/api/products",
        json={
            "name": "Temp Heater",
            "brand": "WarmCo",
            "category_id": category_id,
            "price": 59.0,
            "stock": 1,
        },
    )
    product_id = created.get_json()["id"]
    client.post(
        f"/api/products/{product_id}/specifications",
        json={"spec_name": "Power", "spec_value": "1200 W"},
    )

    client.delete(f"/api/products/{product_id}")
    assert client.get(f"/api/products/{product_id}/specifications").status_code == 404
