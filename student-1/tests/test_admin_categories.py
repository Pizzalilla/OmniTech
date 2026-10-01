from markupsafe import escape


def category_names(client):
    return [category["name"] for category in client.get("/api/categories").get_json()]


def find_category(client, name):
    for category in client.get("/api/categories").get_json():
        if category["name"] == name:
            return category
    return None


def test_admin_page_lists_existing_categories(client):
    page = client.get("/admin")

    assert page.status_code == 200
    body = page.get_data(as_text=True)
    for name in category_names(client):
        # names such as "Ovens & Cooktops" are escaped in the rendered page
        assert str(escape(name)) in body


def test_only_the_admin_page_is_badged_as_admin_view(client):
    admin = client.get("/admin").get_data(as_text=True)
    catalogue = client.get("/").get_data(as_text=True)

    assert "Admin View" in admin
    assert "Shopper view" in admin
    assert "Admin View" not in catalogue


def test_adding_a_category_returns_the_updated_table(client):
    response = client.post(
        "/admin/categories", data={"name": "Dryers", "description": "Vented and heat pump"}
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Dryers" in body
    assert "Vented and heat pump" in body
    assert "Dryers" in category_names(client)


def test_adding_a_category_without_a_name_reports_the_problem(client):
    before = category_names(client)

    response = client.post("/admin/categories", data={"name": "  "})

    # htmx drops the body of an error response, so the fragment comes back as 200
    assert response.status_code == 200
    assert "name is required" in response.get_data(as_text=True)
    assert category_names(client) == before


def test_adding_a_duplicate_category_reports_the_clash(client):
    existing = category_names(client)[0]

    response = client.post("/admin/categories", data={"name": existing})

    assert "already exists" in response.get_data(as_text=True)


def test_edit_returns_the_row_as_a_form(client):
    category = client.get("/api/categories").get_json()[0]

    body = client.get(f"/admin/categories/{category['id']}/edit").get_data(as_text=True)

    assert f'name="name" value="{escape(category["name"])}"' in body
    assert "Save" in body


def test_editing_an_unknown_category_is_not_found(client):
    assert client.get("/admin/categories/9999/edit").status_code == 404


def test_updating_a_category_saves_the_new_name(client):
    category = client.get("/api/categories").get_json()[0]

    response = client.put(
        f"/admin/categories/{category['id']}",
        data={"name": "Renamed", "description": "Now different"},
    )

    assert response.status_code == 200
    assert "Renamed" in response.get_data(as_text=True)
    assert find_category(client, "Renamed") is not None


def test_updating_a_category_without_a_name_keeps_the_row_in_edit_mode(client):
    category = client.get("/api/categories").get_json()[0]

    body = client.put(
        f"/admin/categories/{category['id']}", data={"name": ""}
    ).get_data(as_text=True)

    assert "name is required" in body
    assert f'name="name" value="{escape(category["name"])}"' in body


def test_deleting_an_empty_category_removes_it(client):
    created = client.post("/admin/categories", data={"name": "Temporary"})
    assert created.status_code == 200
    category = find_category(client, "Temporary")

    response = client.delete(f"/admin/categories/{category['id']}")

    assert response.status_code == 200
    assert "Temporary" not in category_names(client)


def test_deleting_a_category_with_products_is_refused(client):
    product = client.get("/api/products").get_json()[0]

    body = client.delete(f"/admin/categories/{product['category_id']}").get_data(
        as_text=True
    )

    assert "still has products" in body
    assert product["category_name"] in category_names(client)


def test_deleting_an_unknown_category_is_not_found(client):
    assert client.delete("/admin/categories/9999").status_code == 404
