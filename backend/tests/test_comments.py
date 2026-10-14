import uuid

import pytest

API = "/api/v1"


def error_code(response) -> str:
    return response.json()["error"]["code"]


def post_comment(client, ticket_id, headers, message="Thanks, any update on this?"):
    return client.post(
        f"{API}/tickets/{ticket_id}/comments", json={"message": message}, headers=headers
    )


@pytest.fixture
def assigned_ticket(customer, agent, make_ticket, assign):
    """A ticket owned by `customer` and assigned to `agent`."""
    ticket = make_ticket(customer["headers"])
    assert assign(ticket["id"], agent["id"]).status_code == 200
    return ticket


# ---------- adding and listing ----------

def test_participants_can_comment(client, admin, agent, customer, assigned_ticket, audit_rows):
    for user in (customer, agent, admin):
        response = post_comment(client, assigned_ticket["id"], user["headers"])
        assert response.status_code == 201
        body = response.json()
        assert body["user"]["id"] == user["id"]
        assert body["ticket_id"] == assigned_ticket["id"]
    assert len(audit_rows("comment_added")) == 3


def test_comments_are_listed_in_chronological_order(client, customer, agent, assigned_ticket):
    post_comment(client, assigned_ticket["id"], customer["headers"], "First message")
    post_comment(client, assigned_ticket["id"], agent["headers"], "Second message")
    response = client.get(
        f"{API}/tickets/{assigned_ticket['id']}/comments", headers=customer["headers"]
    )
    assert response.status_code == 200
    assert [c["message"] for c in response.json()] == ["First message", "Second message"]


def test_outsiders_cannot_comment_or_read(client, customer2, agent2, assigned_ticket):
    for outsider in (customer2, agent2):
        write = post_comment(client, assigned_ticket["id"], outsider["headers"])
        read = client.get(
            f"{API}/tickets/{assigned_ticket['id']}/comments", headers=outsider["headers"]
        )
        for response in (write, read):
            assert response.status_code == 403
            assert error_code(response) == "TICKET_ACCESS_DENIED"


@pytest.mark.parametrize("message", ["", "   ", "x" * 2001])
def test_comment_message_validation(client, customer, assigned_ticket, message):
    response = post_comment(client, assigned_ticket["id"], customer["headers"], message)
    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"


def test_comment_on_unknown_ticket(client, admin):
    response = post_comment(client, uuid.uuid4(), admin["headers"])
    assert response.status_code == 404
    assert error_code(response) == "TICKET_NOT_FOUND"


def test_closed_ticket_rejects_new_comments(client, customer, admin, make_ticket, set_status):
    ticket = make_ticket(customer["headers"])
    set_status(ticket["id"], "in_progress", "resolved", "closed")
    for user in (customer, admin):
        response = post_comment(client, ticket["id"], user["headers"])
        assert response.status_code == 400
        assert error_code(response) == "TICKET_CLOSED"


# ---------- editing, deleting, moderating ----------

def test_author_can_edit_and_delete_own_comment(client, customer, assigned_ticket):
    comment = post_comment(client, assigned_ticket["id"], customer["headers"]).json()

    edited = client.patch(
        f"{API}/comments/{comment['id']}",
        json={"message": "Edited message"},
        headers=customer["headers"],
    )
    assert edited.status_code == 200
    assert edited.json()["message"] == "Edited message"

    deleted = client.delete(f"{API}/comments/{comment['id']}", headers=customer["headers"])
    assert deleted.status_code == 204
    remaining = client.get(
        f"{API}/tickets/{assigned_ticket['id']}/comments", headers=customer["headers"]
    )
    assert remaining.json() == []


def test_users_cannot_modify_other_peoples_comments(
    client, customer, customer2, agent, assigned_ticket
):
    comment = post_comment(client, assigned_ticket["id"], customer["headers"]).json()
    for intruder in (customer2, agent):
        edit = client.patch(
            f"{API}/comments/{comment['id']}",
            json={"message": "Hijacked"},
            headers=intruder["headers"],
        )
        delete = client.delete(f"{API}/comments/{comment['id']}", headers=intruder["headers"])
        for response in (edit, delete):
            assert response.status_code == 403
            assert error_code(response) == "COMMENT_ACCESS_DENIED"


def test_admin_can_moderate_any_comment(client, admin, customer, assigned_ticket):
    comment = post_comment(client, assigned_ticket["id"], customer["headers"]).json()
    edit = client.patch(
        f"{API}/comments/{comment['id']}",
        json={"message": "Moderated by admin"},
        headers=admin["headers"],
    )
    assert edit.status_code == 200
    assert client.delete(f"{API}/comments/{comment['id']}", headers=admin["headers"]).status_code == 204


def test_unknown_comment(client, customer):
    response = client.patch(
        f"{API}/comments/{uuid.uuid4()}", json={"message": "Hello"}, headers=customer["headers"]
    )
    assert response.status_code == 404
    assert error_code(response) == "COMMENT_NOT_FOUND"


# ---------- notifications triggered by comments ----------

def test_comment_notifies_the_other_side(client, customer, agent, assigned_ticket, notification_types):
    post_comment(client, assigned_ticket["id"], customer["headers"])
    assert notification_types(agent["id"]).count("new_comment") == 1
    assert "new_comment" not in notification_types(customer["id"])

    post_comment(client, assigned_ticket["id"], agent["headers"])
    assert notification_types(customer["id"]).count("new_comment") == 1
    assert notification_types(agent["id"]).count("new_comment") == 1  # authors aren't self-notified


def test_comment_on_unassigned_ticket_notifies_nobody_else(
    client, customer, make_ticket, notification_types
):
    ticket = make_ticket(customer["headers"])
    post_comment(client, ticket["id"], customer["headers"])
    assert notification_types(customer["id"]) == ["ticket_created"]