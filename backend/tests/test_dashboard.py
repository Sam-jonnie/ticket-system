from app.core.enums import UserRole

API = "/api/v1"


def stats(client, headers) -> dict:
    response = client.get(f"{API}/dashboard/stats", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_stats_are_scoped_by_role(client, admin, agent, customer, customer2, make_ticket, assign):
    mine = make_ticket(customer["headers"])
    make_ticket(customer["headers"])
    make_ticket(customer2["headers"])
    assign(mine["id"], agent["id"])

    assert stats(client, customer["headers"])["total_tickets"] == 2
    assert stats(client, customer2["headers"])["total_tickets"] == 1
    assert stats(client, agent["headers"])["total_tickets"] == 1
    assert stats(client, admin["headers"])["total_tickets"] == 3


def test_status_and_critical_counts(client, admin, customer, make_ticket, set_status):
    make_ticket(customer["headers"])  # stays open
    in_progress = make_ticket(customer["headers"])
    resolved = make_ticket(customer["headers"], priority="critical")
    closed = make_ticket(customer["headers"])
    set_status(in_progress["id"], "in_progress")
    set_status(resolved["id"], "in_progress", "resolved")
    set_status(closed["id"], "in_progress", "resolved", "closed")

    assert stats(client, admin["headers"]) == {
        "total_tickets": 4,
        "open_tickets": 1,
        "in_progress_tickets": 1,
        "resolved_tickets": 1,
        "closed_tickets": 1,
        "overdue_tickets": 0,
        "critical_tickets": 1,
    }


def test_overdue_counts_only_unfinished_tickets(
    client, admin, customer, make_ticket, set_status, shift_due_date
):
    overdue_open = make_ticket(customer["headers"])
    overdue_resolved = make_ticket(customer["headers"])
    make_ticket(customer["headers"])  # on time
    set_status(overdue_resolved["id"], "in_progress", "resolved")
    shift_due_date(overdue_open["id"], -2)
    shift_due_date(overdue_resolved["id"], -2)

    assert stats(client, admin["headers"])["overdue_tickets"] == 1


def test_admin_dashboard(client, admin, make_user, customer, customer2, agent, make_ticket, assign):
    agent_b = make_user(UserRole.AGENT, name="Agent Two")
    make_user(UserRole.AGENT, name="Retired Agent", is_active=False)
    ticket = make_ticket(customer["headers"])
    assign(ticket["id"], agent["id"])

    response = client.get(f"{API}/dashboard/admin", headers=admin["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["total_customers"] == 2
    assert body["total_agents"] == 3
    assert body["active_agents"] == 2

    per_agent = {row["agent_id"]: row["ticket_count"] for row in body["tickets_per_agent"]}
    assert len(per_agent) == 3  # agents with no tickets are listed too
    assert per_agent[agent["id"]] == 1
    assert per_agent[agent_b["id"]] == 0


def test_agent_dashboard(client, agent, customer, make_ticket, assign, set_status, shift_due_date):
    first = make_ticket(customer["headers"])
    second = make_ticket(customer["headers"])
    assign(first["id"], agent["id"])
    assign(second["id"], agent["id"])
    set_status(second["id"], "in_progress", "resolved")

    response = client.get(f"{API}/dashboard/agent", headers=agent["headers"])
    assert response.status_code == 200
    assert response.json() == {
        "my_open_tickets": 1,
        "my_overdue_tickets": 0,
        "my_resolved_tickets": 1,
    }

    shift_due_date(first["id"], -1)
    again = client.get(f"{API}/dashboard/agent", headers=agent["headers"])
    assert again.json()["my_overdue_tickets"] == 1


def test_dashboard_role_restrictions(client, admin, agent, customer):
    assert client.get(f"{API}/dashboard/admin", headers=agent["headers"]).status_code == 403
    assert client.get(f"{API}/dashboard/admin", headers=customer["headers"]).status_code == 403
    assert client.get(f"{API}/dashboard/agent", headers=customer["headers"]).status_code == 403
    assert client.get(f"{API}/dashboard/agent", headers=admin["headers"]).status_code == 403
    assert client.get(f"{API}/dashboard/stats").status_code in (401, 403)