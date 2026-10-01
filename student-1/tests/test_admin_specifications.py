from markupsafe import escape


def first_product(client):
    return client.get("/api/products").get_json()[0]


def specs(client, product_id):
    return client.get(f"/api/products/{product_id}/specifications").get_json()


def spec_named(client, product_id, name):
    for spec in specs(client, product_id):
        if spec["spec_name"] == name:
            return spec
    return None


def test_page_lists_the_stored_specifications(client):
    product = first_product(client)

    page = client.get(f"/admin/products/{product['id']}/specifications")

    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "Admin View" in body
    for spec in specs(client, product["id"]):
        assert str(escape(spec["spec_name"])) in body


def test_page_offers_the_ai_review_to_the_admin(client):
    product = first_product(client)

    body = client.get(
        f"/admin/products/{product['id']}/specifications"
    ).get_data(as_text=True)

    assert "AI Review" in body
    assert f"/products/{product['id']}/ai-review" in body
    assert "Generating a summary" in body


def test_page_for_an_unknown_product_is_not_found(client):
    assert client.get("/admin/products/9999/specifications").status_code == 404


def test_adding_a_specification_returns_the_updated_table(client):
    product = first_product(client)

    response = client.post(
        f"/admin/products/{product['id']}/specifications",
        data={"spec_name": "Warranty", "spec_value": "5 years"},
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Warranty" in body
    assert "5 years" in body
    assert spec_named(client, product["id"], "Warranty") is not None


def test_adding_a_specification_without_a_value_reports_the_problem(client):
    product = first_product(client)
    before = len(specs(client, product["id"]))

    response = client.post(
        f"/admin/products/{product['id']}/specifications",
        data={"spec_name": "Warranty", "spec_value": "  "},
    )

    # htmx drops the body of an error response, so the fragment comes back as 200
    assert response.status_code == 200
    assert "spec_name and spec_value are required" in response.get_data(as_text=True)
    assert len(specs(client, product["id"])) == before


def test_a_rejected_form_keeps_what_was_typed(client):
    product = first_product(client)

    response = client.post(
        f"/admin/products/{product['id']}/specifications",
        data={"spec_name": "Warranty", "spec_value": ""},
    )

    assert 'value="Warranty"' in response.get_data(as_text=True)


def test_edit_returns_the_row_as_a_form(client):
    product = first_product(client)
    spec = specs(client, product["id"])[0]

    body = client.get(
        f"/admin/products/{product['id']}/specifications/{spec['id']}/edit"
    ).get_data(as_text=True)

    assert f'name="spec_value" value="{escape(spec["spec_value"])}"' in body
    assert "Save" in body


def test_updating_a_specification_saves_the_new_value(client):
    product = first_product(client)
    spec = specs(client, product["id"])[0]

    response = client.put(
        f"/admin/products/{product['id']}/specifications/{spec['id']}",
        data={"spec_name": spec["spec_name"], "spec_value": "changed value"},
    )

    assert response.status_code == 200
    assert "changed value" in response.get_data(as_text=True)


def test_updating_with_a_blank_name_keeps_the_row_in_edit_mode(client):
    product = first_product(client)
    spec = specs(client, product["id"])[0]

    body = client.put(
        f"/admin/products/{product['id']}/specifications/{spec['id']}",
        data={"spec_name": "", "spec_value": "still here"},
    ).get_data(as_text=True)

    assert "are required" in body
    assert "Save" in body


def test_deleting_a_specification_removes_it(client):
    product = first_product(client)
    client.post(
        f"/admin/products/{product['id']}/specifications",
        data={"spec_name": "Temporary", "spec_value": "delete me"},
    )
    spec = spec_named(client, product["id"], "Temporary")

    response = client.delete(
        f"/admin/products/{product['id']}/specifications/{spec['id']}"
    )

    assert response.status_code == 200
    assert spec_named(client, product["id"], "Temporary") is None


def test_a_specification_cannot_be_edited_through_another_product(client):
    products = client.get("/api/products").get_json()
    owner, other = products[0], products[1]
    spec = specs(client, owner["id"])[0]

    edit = client.get(f"/admin/products/{other['id']}/specifications/{spec['id']}/edit")
    update = client.put(
        f"/admin/products/{other['id']}/specifications/{spec['id']}",
        data={"spec_name": "Hijacked", "spec_value": "nope"},
    )
    removal = client.delete(
        f"/admin/products/{other['id']}/specifications/{spec['id']}"
    )

    assert edit.status_code == 404
    assert update.status_code == 404
    assert removal.status_code == 404
    assert spec_named(client, owner["id"], spec["spec_name"]) is not None


def test_cancel_returns_the_plain_table(client):
    product = first_product(client)

    body = client.get(
        f"/admin/products/{product['id']}/specifications/rows"
    ).get_data(as_text=True)

    assert "Add specification" in body
    assert "Save" not in body


def test_the_product_row_links_to_its_specifications(client):
    product = first_product(client)

    body = client.get("/admin").get_data(as_text=True)

    assert f"/admin/products/{product['id']}/specifications" in body
