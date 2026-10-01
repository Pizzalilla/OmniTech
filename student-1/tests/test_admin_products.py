from markupsafe import escape


def products(client):
    return client.get("/api/products").get_json()


def product_named(client, name):
    for product in products(client):
        if product["name"] == name:
            return product
    return None


def new_product_form(client, **overrides):
    category_id = client.get("/api/categories").get_json()[0]["id"]
    form = {
        "name": "TestChill 100",
        "brand": "TestChill",
        "category_id": category_id,
        "price": "499.99",
        "stock": "6",
        "description": "A fridge that only exists in tests.",
        "image_url": "",
    }
    form.update(overrides)
    return form


def test_admin_page_lists_existing_products(client):
    body = client.get("/admin").get_data(as_text=True)

    for product in products(client):
        assert str(escape(product["name"])) in body


def test_adding_a_product_returns_the_updated_table(client):
    response = client.post("/admin/products", data=new_product_form(client))

    assert response.status_code == 200
    assert "TestChill 100" in response.get_data(as_text=True)

    created = product_named(client, "TestChill 100")
    assert created["price"] == 499.99
    assert created["stock"] == 6


def test_adding_a_product_without_a_brand_reports_the_problem(client):
    before = len(products(client))

    response = client.post(
        "/admin/products", data=new_product_form(client, brand="  ")
    )

    # htmx drops the body of an error response, so the fragment comes back as 200
    assert response.status_code == 200
    assert "name and brand are required" in response.get_data(as_text=True)
    assert len(products(client)) == before


def test_adding_a_product_with_a_negative_price_is_refused(client):
    response = client.post("/admin/products", data=new_product_form(client, price="-5"))

    assert "cannot be negative" in response.get_data(as_text=True)
    assert product_named(client, "TestChill 100") is None


def test_adding_a_product_to_an_unknown_category_is_refused(client):
    response = client.post(
        "/admin/products", data=new_product_form(client, category_id="9999")
    )

    assert "category not found" in response.get_data(as_text=True)
    assert product_named(client, "TestChill 100") is None


def test_a_rejected_form_keeps_what_was_typed(client):
    response = client.post(
        "/admin/products", data=new_product_form(client, brand="", name="Typed Name")
    )

    # retyping every field after one mistake would be miserable
    assert 'value="Typed Name"' in response.get_data(as_text=True)


def test_edit_prefills_the_form_with_the_stored_values(client):
    product = products(client)[0]

    body = client.get(f"/admin/products/{product['id']}/edit").get_data(as_text=True)

    assert "Edit product" in body
    assert f'value="{escape(product["name"])}"' in body
    assert f'value="{escape(product["brand"])}"' in body
    assert "Save changes" in body


def test_editing_an_unknown_product_is_not_found(client):
    assert client.get("/admin/products/9999/edit").status_code == 404


def test_updating_a_product_saves_the_new_values(client):
    product = products(client)[0]

    response = client.put(
        f"/admin/products/{product['id']}",
        data=new_product_form(
            client, name="Renamed Appliance", stock="42", category_id=product["category_id"]
        ),
    )

    assert response.status_code == 200
    updated = product_named(client, "Renamed Appliance")
    assert updated["stock"] == 42
    assert updated["id"] == product["id"]


def test_updating_a_product_with_a_bad_price_stays_in_edit_mode(client):
    product = products(client)[0]

    body = client.put(
        f"/admin/products/{product['id']}", data=new_product_form(client, price="abc")
    ).get_data(as_text=True)

    assert "must be valid numbers" in body
    assert "Save changes" in body


def test_deleting_a_product_removes_it_and_its_specifications(client):
    client.post("/admin/products", data=new_product_form(client))
    created = product_named(client, "TestChill 100")
    client.post(
        f"/api/products/{created['id']}/specifications",
        json={"spec_name": "Capacity", "spec_value": "100 L"},
    )

    response = client.delete(f"/admin/products/{created['id']}")

    assert response.status_code == 200
    assert product_named(client, "TestChill 100") is None
    assert client.get(f"/api/products/{created['id']}/specifications").status_code == 404


def test_deleting_an_unknown_product_is_not_found(client):
    assert client.delete("/admin/products/9999").status_code == 404
