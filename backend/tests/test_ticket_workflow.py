import uuid

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.ticket_status_history import TicketStatusHistory

API = "/api/v1"


def error_code(response) -> str:
    return response.json()["error"]["code"]


def history_rows(ticket_id: str) -> list[TicketStatusHistory]:
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(TicketStatusHistory)
                .where(TicketStatusHistory.ticket_id == uuid.UUID(ticket_id))
                .order_by(TicketStatusHistory.created_at)
            ).all()
        )


def change_status(client, ticket_id, new_status, headers):
    return client.patch(
        f"{API}/tickets/{ticket_id}/status", json={"status": new_status}, headers=headers
    )


# ---------- assignment ----------

def test_admin_assigns_ticket_to_agent(client, agent, customer, make_ticket, assign):
    ticket = make_ticket(customer["headers"])
    response = assign(ticket["id"], agent["id"])
    assert response.status_code == 200
    assert response.json()["assigned_agent"]["id"] == agent["id"]
    assert response.json()["status"] == "open"


def test_agent_can_assign_tickets(client, agent, agent2, customer, make_ticket, assign):
    ticket = make_ticket(customer["headers"])
    response = assign(ticket["id"], agent2["id"], headers=agent["headers"])
    assert response.status_code == 200


def test_customer_cannot_assign(client, agent, customer, make_ticket, assign):
    ticket = make_ticket(customer["headers"])
    response = assign(ticket["id"], agent["id"], headers=customer["headers"])
    assert response.status_code == 403
    assert error_code(response) == "INSUFFICIENT_ROLE"


def test_inactive_agent_cannot_receive_tickets(client, make_user, customer, make_ticket, assign):
    from app.core.enums import UserRole

    inactive = make_user(UserRole.AGENT, is_active=False)
    ticket = make_ticket(customer["headers"])
    response = assign(ticket["id"], inactive["id"])
    assert response.status_code == 400
    assert error_code(response) == "AGENT_INACTIVE"


def test_cannot_assign_to_non_agent(client, admin, customer, make_ticket, assign):
    ticket = make_ticket(customer["headers"])
    for target in (customer["id"], admin["id"], str(uuid.uuid4())):
        response = assign(ticket["id"], target)
        assert response.status_code == 404
        assert error_code(response) == "AGENT_NOT_FOUND"


def test_assign_unknown_ticket(client, agent, assign):
    response = assign(str(uuid.uuid4()), agent["id"])
    assert response.status_code == 404
    assert error_code(response) == "TICKET_NOT_FOUND"


def test_reassignment_is_recorded_and_notified(
    client, agent, agent2, customer, make_ticket, assign, notification_types
):
    ticket = make_ticket(customer["headers"])
    assign(ticket["id"], agent["id"])
    assign(ticket["id"], agent2["id"])

    rows = history_rows(ticket["id"])
    assert len(rows) == 2
    assert rows[0].old_agent_id is None and str(rows[0].new_agent_id) == agent["id"]
    assert str(rows[1].old_agent_id) == agent["id"] and str(rows[1].new_agent_id) == agent2["id"]

    assert notification_types(agent["id"]) == ["ticket_assigned"]
    assert notification_types(agent2["id"]) == ["ticket_reassigned"]


# ---------- status transitions ----------

def test_full_happy_path_by_assigned_agent(client, agent, customer, make_ticket, assign):
    ticket = make_ticket(customer["headers"])
    assign(ticket["id"], agent["id"])
    for new_status in ("in_progress", "resolved", "closed"):
        response = change_status(client, ticket["id"], new_status, agent["headers"])
        assert response.status_code == 200
        assert response.json()["status"] == new_status


def test_allowed_backward_moves(client, admin, customer, make_ticket, set_status):
    ticket = make_ticket(customer["headers"])
    set_status(ticket["id"], "in_progress", "open", "in_progress", "resolved")
    reopen = change_status(client, ticket["id"], "in_progress", admin["headers"])
    assert reopen.status_code == 200  # a resolved ticket can be reopened


INVALID_TRANSITIONS = [
    ([], "resolved"),
    ([], "closed"),
    ([], "open"),
    (["in_progress"], "closed"),
    (["in_progress", "resolved"], "open"),
    (["in_progress", "resolved", "closed"], "in_progress"),
    (["in_progress", "resolved", "closed"], "open"),
]


@pytest.mark.parametrize("path,target", INVALID_TRANSITIONS)
def test_invalid_status_transitions_rejected(
    client, admin, customer, make_ticket, set_status, path, target
):
    ticket = make_ticket(customer["headers"])
    set_status(ticket["id"], *path)
    response = change_status(client, ticket["id"], target, admin["headers"])
    assert response.status_code == 400
    assert error_code(response) == "INVALID_STATUS_TRANSITION"
    assert response.json()["success"] is False


def test_unknown_status_value_rejected(client, admin, customer, make_ticket):
    ticket = make_ticket(customer["headers"])
    response = change_status(client, ticket["id"], "teleported", admin["headers"])
    assert response.status_code == 422


def test_customer_cannot_change_status(client, customer, make_ticket):
    ticket = make_ticket(customer["headers"])
    response = change_status(client, ticket["id"], "in_progress", customer["headers"])
    assert response.status_code == 403
    assert error_code(response) == "INSUFFICIENT_ROLE"


def test_unassigned_agent_cannot_touch_ticket(client, agent, agent2, customer, make_ticket, assign):
    ticket = make_ticket(customer["headers"])
    assign(ticket["id"], agent["id"])
    response = change_status(client, ticket["id"], "in_progress", agent2["headers"])
    assert response.status_code == 403
    assert error_code(response) == "TICKET_ACCESS_DENIED"


def test_status_history_and_audit_trail(
    client, admin, customer, make_ticket, set_status, audit_rows
):
    ticket = make_ticket(customer["headers"])
    set_status(ticket["id"], "in_progress", "resolved", "closed")

    rows = history_rows(ticket["id"])
    assert [(r.old_status.value, r.new_status.value) for r in rows] == [
        ("open", "in_progress"),
        ("in_progress", "resolved"),
        ("resolved", "closed"),
    ]
    assert len(audit_rows("status_changed")) == 3
    assert len(audit_rows("ticket_closed")) == 1