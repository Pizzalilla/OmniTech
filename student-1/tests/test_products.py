import pytest


@pytest.fixture()
def new_product(client):
    category_id = client.get("/api/categories").get_json()[0]["id"]
    return {
        "name": "Desk Fan 200",
        "brand": "BreezeCo",
        "category_id": category_id,
        "price": 99.5,
        "stock": 5,
        "description": "Small desk fan",
    }


def test_seed_meets_minimum_record_count(client):
    response = client.get("/api/products")
    assert response.status_code == 200
    products = response.get_json()
    assert len(products) >= 10
    by_category = {}
    by_brand = {}
    for product in products:
        by_category[product["category_id"]] = by_category.get(product["category_id"], 0) + 1
        by_brand[product["brand"]] = by_brand.get(product["brand"], 0) + 1
    assert all(count >= 2 for count in by_category.values())
    assert all(count >= 2 for count in by_brand.values())


def test_product_includes_its_category_name(client):
    product = client.get("/api/products/1").get_json()
    category = client.get(f"/api/categories/{product['category_id']}").get_json()
    assert product["category_name"] == category["name"]


def test_filter_by_category(client):
    category_id = client.get("/api/products").get_json()[0]["category_id"]
    products = client.get(f"/api/products?category_id={category_id}").get_json()
    assert products
    assert all(p["category_id"] == category_id for p in products)


def test_filter_by_brand_ignores_case(client):
    brand = client.get("/api/products").get_json()[0]["brand"]
    products = client.get(f"/api/products?brand={brand.lower()}").get_json()
    assert products
    assert all(p["brand"].lower() == brand.lower() for p in products)


def test_filter_accepts_more_than_one_brand(client):
    products = client.get("/api/products").get_json()
    first = products[0]["brand"]
    other = next(item["brand"] for item in products if item["brand"] != first)
    filtered = client.get(f"/api/products?brand={first}&brand={other}").get_json()
    allowed = {first.lower(), other.lower()}
    assert filtered
    assert all(item["brand"].lower() in allowed for item in filtered)


def test_filter_by_price_range(client):
    products = client.get("/api/products?min_price=500&max_price=900").get_json()
    assert products
    assert all(500 <= p["price"] <= 900 for p in products)


def test_search_matches_product_name(client):
    name = client.get("/api/products").get_json()[0]["name"]
    products = client.get(f"/api/products?search={name[:6]}").get_json()
    assert any(p["name"] == name for p in products)


def test_filter_by_spec_keyword(client):
    specs = client.get("/api/products/1/specifications").get_json()
    keyword = specs[0]["spec_value"]
    products = client.get(f"/api/products?spec_keyword={keyword}").get_json()
    assert any(p["id"] == 1 for p in products)


def test_create_update_and_delete_product(client, new_product):
    created = client.post("/api/products", json=new_product)
    assert created.status_code == 201
    product_id = created.get_json()["id"]

    updated = client.put(
        f"/api/products/{product_id}",
        json={**new_product, "price": 120.0, "stock": 2},
    )
    assert updated.status_code == 200
    assert updated.get_json()["price"] == 120.0

    assert client.delete(f"/api/products/{product_id}").status_code == 204
    assert client.get(f"/api/products/{product_id}").status_code == 404


def test_create_product_requires_name_and_brand(client, new_product):
    response = client.post("/api/products", json={**new_product, "brand": ""})
    assert response.status_code == 400


def test_create_product_rejects_unknown_category(client, new_product):
    response = client.post("/api/products", json={**new_product, "category_id": 999})
    assert response.status_code == 400


def test_create_product_rejects_negative_price(client, new_product):
    response = client.post("/api/products", json={**new_product, "price": -1})
    assert response.status_code == 400
