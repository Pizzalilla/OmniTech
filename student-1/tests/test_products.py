NEW_PRODUCT = {
    "name": "Desk Fan 200",
    "brand": "BreezeCo",
    "category_id": 3,
    "price": 99.5,
    "stock": 5,
    "description": "Small desk fan",
}


def test_seeded_products_are_listed(client):
    response = client.get("/api/products")
    assert response.status_code == 200
    assert len(response.get_json()) == 3


def test_product_includes_category_name(client):
    product = client.get("/api/products/1").get_json()
    assert product["category_name"] == "Air Conditioners"


def test_filter_by_category(client):
    products = client.get("/api/products?category_id=1").get_json()
    assert [p["name"] for p in products] == ["FreshKeep XL"]


def test_filter_by_brand_ignores_case(client):
    products = client.get("/api/products?brand=coolbreeze").get_json()
    assert [p["name"] for p in products] == ["CoolBreeze 5000"]


def test_filter_by_price_range(client):
    products = client.get("/api/products?min_price=700&max_price=800").get_json()
    assert [p["name"] for p in products] == ["SpinMaster Pro 10"]


def test_create_update_and_delete_product(client):
    created = client.post("/api/products", json=NEW_PRODUCT)
    assert created.status_code == 201
    product_id = created.get_json()["id"]

    updated = client.put(
        f"/api/products/{product_id}",
        json={**NEW_PRODUCT, "price": 120.0, "stock": 2},
    )
    assert updated.status_code == 200
    assert updated.get_json()["price"] == 120.0

    assert client.delete(f"/api/products/{product_id}").status_code == 204
    assert client.get(f"/api/products/{product_id}").status_code == 404


def test_create_product_requires_name_and_brand(client):
    response = client.post("/api/products", json={**NEW_PRODUCT, "brand": ""})
    assert response.status_code == 400


def test_create_product_rejects_unknown_category(client):
    response = client.post("/api/products", json={**NEW_PRODUCT, "category_id": 999})
    assert response.status_code == 400


def test_create_product_rejects_negative_price(client):
    response = client.post("/api/products", json={**NEW_PRODUCT, "price": -1})
    assert response.status_code == 400
