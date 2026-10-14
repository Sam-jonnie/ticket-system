import uuid

API = "/api/v1"


def error_code(response) -> str:
    return response.json()["error"]["code"]


def test_admin_creates_category_and_duplicate_rejected(client, admin):
    payload = {"name": "Billing", "description": "Invoices and payments"}
    ok = client.post(f"{API}/categories", json=payload, headers=admin["headers"])
    assert ok.status_code == 201 and ok.json()["is_active"] is True

    duplicate = client.post(f"{API}/categories", json=payload, headers=admin["headers"])
    assert duplicate.status_code == 409
    assert error_code(duplicate) == "CATEGORY_ALREADY_EXISTS"


def test_non_admin_cannot_manage_categories(client, customer, agent, category):
    for user in (customer, agent):
        create = client.post(f"{API}/categories", json={"name": "Nope"}, headers=user["headers"])
        assert create.status_code == 403
        deactivate = client.patch(
            f"{API}/categories/{category['id']}/deactivate", headers=user["headers"]
        )
        assert deactivate.status_code == 403


def test_list_categories_requires_login_and_supports_active_filter(
    client, customer, admin, category, make_category
):
    assert client.get(f"{API}/categories").status_code in (401, 403)

    client.patch(f"{API}/categories/{category['id']}/deactivate", headers=admin["headers"])
    make_category("Billing")

    everything = client.get(f"{API}/categories", headers=customer["headers"]).json()
    active = client.get(
        f"{API}/categories", params={"active_only": True}, headers=customer["headers"]
    ).json()
    assert len(everything) == 2
    assert [c["name"] for c in active] == ["Billing"]


def test_update_and_reactivate_category(client, admin, category):
    updated = client.patch(
        f"{API}/categories/{category['id']}", json={"name": "Tech Help"}, headers=admin["headers"]
    )
    assert updated.status_code == 200 and updated.json()["name"] == "Tech Help"

    client.patch(f"{API}/categories/{category['id']}/deactivate", headers=admin["headers"])
    reactivated = client.patch(f"{API}/categories/{category['id']}/activate", headers=admin["headers"])
    assert reactivated.json()["is_active"] is True


def test_inactive_category_rejected_for_new_tickets(client, customer, admin, category):
    client.patch(f"{API}/categories/{category['id']}/deactivate", headers=admin["headers"])
    response = client.post(
        f"{API}/tickets",
        json={
            "title": "Printer is broken",
            "description": "The office printer will not print anything.",
            "category_id": category["id"],
            "priority_name": "low",
        },
        headers=customer["headers"],
    )
    assert response.status_code == 400
    assert error_code(response) == "CATEGORY_INACTIVE"


def test_unknown_category_rejected_for_new_tickets(client, customer):
    response = client.post(
        f"{API}/tickets",
        json={
            "title": "Printer is broken",
            "description": "The office printer will not print anything.",
            "category_id": str(uuid.uuid4()),
            "priority_name": "low",
        },
        headers=customer["headers"],
    )
    assert response.status_code == 404
    assert error_code(response) == "CATEGORY_NOT_FOUND"