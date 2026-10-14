import pytest
from starlette.websockets import WebSocketDisconnect

API = "/api/v1"


def error_code(response) -> str:
    return response.json()["error"]["code"]


def my_notifications(client, headers, **params) -> list[dict]:
    response = client.get(f"{API}/notifications", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_creating_a_ticket_notifies_the_customer(client, customer, make_ticket):
    ticket = make_ticket(customer["headers"])
    notifications = my_notifications(client, customer["headers"])
    assert len(notifications) == 1
    assert notifications[0]["type"] == "ticket_created"
    assert notifications[0]["ticket_id"] == ticket["id"]
    assert notifications[0]["is_read"] is False


def test_mark_one_notification_as_read(client, customer, make_ticket):
    make_ticket(customer["headers"])
    notification = my_notifications(client, customer["headers"])[0]

    response = client.patch(
        f"{API}/notifications/{notification['id']}/read", headers=customer["headers"]
    )
    assert response.status_code == 200
    assert response.json()["is_read"] is True
    assert my_notifications(client, customer["headers"], unread_only=True) == []
    assert len(my_notifications(client, customer["headers"])) == 1


def test_mark_all_as_read(client, customer, make_ticket):
    make_ticket(customer["headers"])
    make_ticket(customer["headers"])
    assert len(my_notifications(client, customer["headers"], unread_only=True)) == 2

    response = client.patch(f"{API}/notifications/read-all", headers=customer["headers"])
    assert response.status_code == 200
    assert response.json() == {"marked_read": 2}
    assert my_notifications(client, customer["headers"], unread_only=True) == []


def test_notifications_belong_to_their_owner(client, customer, customer2, make_ticket):
    make_ticket(customer["headers"])
    notification = my_notifications(client, customer["headers"])[0]

    assert my_notifications(client, customer2["headers"]) == []
    response = client.patch(
        f"{API}/notifications/{notification['id']}/read", headers=customer2["headers"]
    )
    assert response.status_code == 404
    assert error_code(response) == "NOTIFICATION_NOT_FOUND"


def test_status_changes_notify_the_customer(client, customer, make_ticket, set_status, notification_types):
    ticket = make_ticket(customer["headers"])
    set_status(ticket["id"], "in_progress", "resolved", "closed")
    assert notification_types(customer["id"]) == [
        "status_changed",
        "ticket_closed",
        "ticket_created",
        "ticket_resolved",
    ]


def test_notifications_require_authentication(client):
    assert client.get(f"{API}/notifications").status_code in (401, 403)


# ---------- WebSocket authentication ----------

def test_websocket_rejects_invalid_token(client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/notifications?token=not-a-token"):
            pass
    assert exc_info.value.code == 4001


def test_websocket_rejects_refresh_token(client, customer):
    login = client.post(
        f"{API}/auth/login", json={"email": customer["email"], "password": customer["password"]}
    ).json()
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/notifications?token={login['refresh_token']}"):
            pass
    assert exc_info.value.code == 4001


def test_websocket_accepts_valid_access_token(client, customer):
    with client.websocket_connect(f"/ws/notifications?token={customer['token']}"):
        pass  # connected and closed cleanly