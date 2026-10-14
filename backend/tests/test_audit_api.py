import pytest

API = "/api/v1"


def test_admin_can_list_and_filter_audit_logs(client, admin, customer, make_ticket):
    ticket = make_ticket(customer["headers"])

    response = client.get(
        f"{API}/audit-logs", params={"action": "ticket_created"}, headers=admin["headers"]
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["action"] == "ticket_created"
    assert item["entity"] == "ticket" and item["entity_id"] == ticket["id"]
    assert item["user_id"] == customer["id"]
    assert item["ip_address"] == "127.0.0.1"
    assert item["metadata"]["ticket_number"] == "TKT-00001"
    assert "metadata_" not in item


def test_filters_pagination_and_newest_first(
    client, admin, customer, customer2, make_ticket, set_status
):
    first = make_ticket(customer["headers"])
    make_ticket(customer2["headers"])
    set_status(first["id"], "in_progress")  # 3 audit rows in total

    def fetch(**params) -> dict:
        response = client.get(f"{API}/audit-logs", params=params, headers=admin["headers"])
        assert response.status_code == 200, response.text
        return response.json()

    assert fetch(user_id=customer["id"])["total"] == 1
    assert fetch(entity_id=first["id"])["total"] == 2  # created + status_changed

    page = fetch(page=1, page_size=1)
    assert page["total"] == 3 and len(page["items"]) == 1
    assert page["items"][0]["action"] == "status_changed"  # newest first


def test_only_admins_can_read_audit_logs(client, agent, customer):
    for user in (agent, customer):
        assert client.get(f"{API}/audit-logs", headers=user["headers"]).status_code == 403
    assert client.get(f"{API}/audit-logs").status_code in (401, 403)


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_audit_logs_cannot_be_modified_by_anyone(client, admin, method):
    response = getattr(client, method)(f"{API}/audit-logs", headers=admin["headers"])
    assert response.status_code == 405  # the route only allows GET