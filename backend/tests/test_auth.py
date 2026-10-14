from datetime import datetime, timedelta, timezone
import uuid

import pytest
from jose import jwt

from app.core.config import settings

API = "/api/v1"


def register(client, email="newuser@example.com", password="Password123!", name="New User", **extra):
    return client.post(
        f"{API}/auth/register",
        json={"name": name, "email": email, "password": password, **extra},
    )


def login(client, email, password):
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


def error_code(response) -> str:
    return response.json()["error"]["code"]


def login_tokens(client, user) -> dict:
    response = login(client, user["email"], user["password"])
    assert response.status_code == 200, response.text
    return response.json()


# ---------- registration ----------

def test_register_success(client):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "newuser@example.com"
    assert body["role"] == "customer"
    assert body["is_active"] is True
    assert "password" not in body and "hashed_password" not in body


def test_register_cannot_choose_role(client):
    response = register(client, role="admin")
    assert response.status_code == 201
    assert response.json()["role"] == "customer"


def test_register_duplicate_email_rejected(client):
    assert register(client).status_code == 201
    response = register(client)
    assert response.status_code == 409
    assert error_code(response) == "EMAIL_ALREADY_EXISTS"
    assert response.json()["success"] is False


def test_register_duplicate_email_is_case_insensitive(client):
    assert register(client, email="Dup@Example.com").status_code == 201
    assert register(client, email="dup@example.com").status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "A", "email": "ok@example.com", "password": "Password123!"},
        {"name": "Valid Name", "email": "not-an-email", "password": "Password123!"},
        {"name": "Valid Name", "email": "ok@example.com", "password": "short"},
        {"name": "Valid Name", "email": "ok@example.com"},
    ],
)
def test_register_validation_errors(client, payload):
    response = client.post(f"{API}/auth/register", json=payload)
    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"


# ---------- login ----------

def test_login_success(client, customer):
    response = login(client, customer["email"], customer["password"])
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_wrong_password_rejected(client, customer):
    response = login(client, customer["email"], "WrongPassword1!")
    assert response.status_code == 401
    assert error_code(response) == "INVALID_CREDENTIALS"


def test_login_unknown_email_gives_same_error(client):
    response = login(client, "nobody@example.com", "Password123!")
    assert response.status_code == 401
    assert error_code(response) == "INVALID_CREDENTIALS"


def test_inactive_user_cannot_login(client, make_user):
    inactive = make_user(is_active=False)
    response = login(client, inactive["email"], inactive["password"])
    assert response.status_code == 403
    assert error_code(response) == "ACCOUNT_INACTIVE"


# ---------- token validation ----------

def test_me_returns_current_user(client, customer):
    response = client.get(f"{API}/auth/me", headers=customer["headers"])
    assert response.status_code == 200
    assert response.json()["id"] == customer["id"]


def test_protected_route_requires_token(client):
    response = client.get(f"{API}/auth/me")
    # FastAPI's HTTPBearer answers 403 on older versions and 401 on newer ones
    assert response.status_code in (401, 403)
    assert response.json()["success"] is False


def test_garbage_token_rejected(client):
    response = client.get(f"{API}/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert response.status_code == 401
    assert error_code(response) == "INVALID_TOKEN"


def test_expired_token_rejected(client, customer):
    expired = jwt.encode(
        {
            "sub": customer["id"],
            "role": "customer",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    response = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert error_code(response) == "INVALID_TOKEN"


def test_token_signed_with_wrong_secret_rejected(client, customer):
    forged = jwt.encode(
        {
            "sub": customer["id"],
            "role": "admin",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "some-other-secret",
        algorithm=settings.algorithm,
    )
    response = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_token_for_unknown_user_rejected(client):
    ghost = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "role": "customer",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    response = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {ghost}"})
    assert response.status_code == 401


def test_refresh_token_cannot_be_used_as_access_token(client, customer):
    tokens = login_tokens(client, customer)
    response = client.get(
        f"{API}/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
    )
    assert response.status_code == 401
    assert error_code(response) == "INVALID_TOKEN"


def test_access_token_cannot_be_used_to_refresh(client, customer):
    tokens = login_tokens(client, customer)
    response = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert response.status_code == 401
    assert error_code(response) == "INVALID_REFRESH_TOKEN"


def test_deactivated_users_existing_token_stops_working(client, admin, customer):
    deactivate = client.patch(f"{API}/users/{customer['id']}/deactivate", headers=admin["headers"])
    assert deactivate.status_code == 200
    response = client.get(f"{API}/auth/me", headers=customer["headers"])
    assert response.status_code == 401
    assert error_code(response) == "USER_INACTIVE"


# ---------- refresh, logout, change password ----------

def test_refresh_rotation_makes_old_token_unusable(client, customer):
    tokens = login_tokens(client, customer)
    first = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    assert first.json()["refresh_token"] != tokens["refresh_token"]

    reuse = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401
    assert error_code(reuse) == "INVALID_REFRESH_TOKEN"


def test_logout_revokes_refresh_token(client, customer):
    tokens = login_tokens(client, customer)
    response = client.post(
        f"{API}/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    refresh = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 401


def test_change_password_flow(client, customer):
    tokens = login_tokens(client, customer)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    wrong = client.post(
        f"{API}/auth/change-password",
        json={"current_password": "Wrong123!", "new_password": "NewPassword456!"},
        headers=headers,
    )
    assert wrong.status_code == 401

    ok = client.post(
        f"{API}/auth/change-password",
        json={"current_password": customer["password"], "new_password": "NewPassword456!"},
        headers=headers,
    )
    assert ok.status_code == 200

    assert login(client, customer["email"], customer["password"]).status_code == 401
    assert login(client, customer["email"], "NewPassword456!").status_code == 200
    # Changing the password signs the user out everywhere
    old_refresh = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert old_refresh.status_code == 401