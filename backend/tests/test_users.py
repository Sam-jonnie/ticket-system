import uuid

API = "/api/v1"


def error_code(response) -> str:
    return response.json()["error"]["code"]


def new_user_payload(**overrides) -> dict:
    return {
        "name": "Created User",
        "email": "created@example.com",
        "password": "Password123!",
        "role": "agent",
        **overrides,
    }


def test_admin_creates_user_with_any_role(client, admin, audit_rows):
    response = client.post(f"{API}/users", json=new_user_payload(), headers=admin["headers"])
    assert response.status_code == 201
    assert response.json()["role"] == "agent"
    assert [r.action.value for r in audit_rows("user_created")] == ["user_created"]


def test_non_admins_cannot_create_users(client, customer, agent):
    for user in (customer, agent):
        response = client.post(f"{API}/users", json=new_user_payload(), headers=user["headers"])
        assert response.status_code == 403
        assert error_code(response) == "INSUFFICIENT_ROLE"


def test_user_endpoints_require_authentication(client):
    assert client.get(f"{API}/users").status_code in (401, 403)


def test_admin_create_duplicate_email_rejected(client, admin, customer):
    response = client.post(
        f"{API}/users", json=new_user_payload(email=customer["email"]), headers=admin["headers"]
    )
    assert response.status_code == 409
    assert error_code(response) == "EMAIL_ALREADY_EXISTS"


def test_list_users_pagination_and_role_filter(client, admin, make_user):
    from app.core.enums import UserRole

    for _ in range(3):
        make_user(UserRole.AGENT)

    page1 = client.get(f"{API}/users", params={"page": 1, "page_size": 2}, headers=admin["headers"])
    assert page1.status_code == 200
    body = page1.json()
    assert body["total"] == 4  # admin + 3 agents
    assert len(body["items"]) == 2

    page2 = client.get(f"{API}/users", params={"page": 2, "page_size": 2}, headers=admin["headers"])
    assert len(page2.json()["items"]) == 2

    agents = client.get(f"{API}/users", params={"role": "agent"}, headers=admin["headers"])
    assert agents.json()["total"] == 3


def test_get_user_and_not_found(client, admin, customer):
    ok = client.get(f"{API}/users/{customer['id']}", headers=admin["headers"])
    assert ok.status_code == 200 and ok.json()["email"] == customer["email"]

    missing = client.get(f"{API}/users/{uuid.uuid4()}", headers=admin["headers"])
    assert missing.status_code == 404
    assert error_code(missing) == "USER_NOT_FOUND"


def test_update_user_and_email_conflict(client, admin, customer, customer2, audit_rows):
    ok = client.patch(
        f"{API}/users/{customer['id']}", json={"name": "Renamed User"}, headers=admin["headers"]
    )
    assert ok.status_code == 200 and ok.json()["name"] == "Renamed User"
    assert len(audit_rows("user_updated")) == 1

    conflict = client.patch(
        f"{API}/users/{customer['id']}", json={"email": customer2["email"]}, headers=admin["headers"]
    )
    assert conflict.status_code == 409


def test_deactivate_blocks_login_and_activate_restores_it(client, admin, customer):
    client.patch(f"{API}/users/{customer['id']}/deactivate", headers=admin["headers"])
    blocked = client.post(
        f"{API}/auth/login", json={"email": customer["email"], "password": customer["password"]}
    )
    assert blocked.status_code == 403

    client.patch(f"{API}/users/{customer['id']}/activate", headers=admin["headers"])
    restored = client.post(
        f"{API}/auth/login", json={"email": customer["email"], "password": customer["password"]}
    )
    assert restored.status_code == 200


def test_change_role(client, admin, customer):
    response = client.patch(
        f"{API}/users/{customer['id']}/role", json={"role": "agent"}, headers=admin["headers"]
    )
    assert response.status_code == 200
    assert response.json()["role"] == "agent"


def test_admin_cannot_lock_themselves_out(client, admin):
    deactivate = client.patch(f"{API}/users/{admin['id']}/deactivate", headers=admin["headers"])
    assert deactivate.status_code == 400
    assert error_code(deactivate) == "SELF_DEACTIVATION"

    demote = client.patch(
        f"{API}/users/{admin['id']}/role", json={"role": "customer"}, headers=admin["headers"]
    )
    assert demote.status_code == 400
    assert error_code(demote) == "SELF_DEMOTION"