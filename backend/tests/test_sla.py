import csv
import io
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.tasks.sla_tasks import check_sla_breaches
from app.utils.sla import calculate_due_date, is_overdue

API = "/api/v1"
CREATED = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
NOTHING = {"warnings": 0, "breaches": 0, "escalations": 0}


# ---------- pure calculation (no database) ----------

@pytest.mark.parametrize("hours", [72, 48, 24, 4])
def test_due_date_is_creation_time_plus_sla(hours):
    priority = SimpleNamespace(sla_hours=hours)
    assert calculate_due_date(priority, CREATED) == CREATED + timedelta(hours=hours)


def test_due_date_defaults_to_now():
    before = datetime.now(timezone.utc)
    due = calculate_due_date(SimpleNamespace(sla_hours=1))
    assert before + timedelta(hours=1) <= due <= datetime.now(timezone.utc) + timedelta(hours=1)


@pytest.mark.parametrize(
    "due_offset_hours,status,expected",
    [
        (-1, "open", True),
        (-1, "in_progress", True),
        (-1, "resolved", False),
        (-1, "closed", False),
        (1, "open", False),
    ],
)
def test_is_overdue(due_offset_hours, status, expected):
    due = datetime.now(timezone.utc) + timedelta(hours=due_offset_hours)
    assert is_overdue(due, status) is expected


def test_ticket_without_due_date_is_never_overdue():
    assert is_overdue(None, "open") is False


# ---------- through the API ----------

@pytest.mark.parametrize(
    "priority,hours", [("low", 72), ("medium", 48), ("high", 24), ("critical", 4)]
)
def test_new_ticket_due_date_matches_priority_sla(client, customer, make_ticket, priority, hours):
    ticket = make_ticket(customer["headers"], priority=priority)
    assert ticket["priority"]["sla_hours"] == hours
    gap = datetime.fromisoformat(ticket["due_date"]) - datetime.fromisoformat(ticket["created_at"])
    assert abs(gap - timedelta(hours=hours)) < timedelta(seconds=5)


def test_overdue_is_flagged_in_csv_export(client, admin, customer, make_ticket, shift_due_date):
    late = make_ticket(customer["headers"], title="Late ticket here")
    make_ticket(customer["headers"], title="Fresh ticket here")
    shift_due_date(late["id"], -3)

    response = client.get(f"{API}/tickets/export", headers=admin["headers"])
    rows = {row["title"]: row for row in csv.DictReader(io.StringIO(response.text))}
    assert rows["Late ticket here"]["overdue"] == "yes"
    assert rows["Fresh ticket here"]["overdue"] == "no"


# ---------- the scheduled job (called directly, no Celery worker needed) ----------

@pytest.fixture
def critical_ticket(customer, agent, make_ticket, assign):
    """A critical (4h SLA) ticket owned by `customer`, assigned to `agent`."""
    ticket = make_ticket(customer["headers"], priority="critical")
    assert assign(ticket["id"], agent["id"]).status_code == 200
    return ticket


def test_fresh_ticket_triggers_nothing(critical_ticket):
    assert check_sla_breaches() == NOTHING


def test_warning_goes_to_assigned_agent_once(
    critical_ticket, customer, agent, shift_due_date, notification_types
):
    shift_due_date(critical_ticket["id"], 0.5)  # 87% of the 4h window used
    assert check_sla_breaches() == {"warnings": 1, "breaches": 0, "escalations": 0}
    assert notification_types(agent["id"]) == ["sla_warning", "ticket_assigned"]
    assert notification_types(customer["id"]) == ["ticket_created"]
    assert check_sla_breaches() == NOTHING  # fires once per ticket


def test_unassigned_warning_goes_to_admins(
    admin, customer, make_ticket, shift_due_date, notification_types
):
    ticket = make_ticket(customer["headers"], priority="critical")
    shift_due_date(ticket["id"], 0.5)
    assert check_sla_breaches()["warnings"] == 1
    assert notification_types(admin["id"]) == ["sla_warning"]


def test_breach_notifies_customer_and_agent(
    critical_ticket, admin, customer, agent, shift_due_date, notification_types
):
    shift_due_date(critical_ticket["id"], -1)  # 1h late: breached, not yet escalated
    assert check_sla_breaches() == {"warnings": 0, "breaches": 1, "escalations": 0}
    assert notification_types(customer["id"]) == ["sla_breached", "ticket_created"]
    assert notification_types(agent["id"]) == ["sla_breached", "ticket_assigned"]
    assert notification_types(admin["id"]) == []
    assert check_sla_breaches() == NOTHING


def test_long_overdue_ticket_escalates_to_admins(
    critical_ticket, admin, shift_due_date, notification_types
):
    shift_due_date(critical_ticket["id"], -3)  # escalation starts 2h after the due date
    assert check_sla_breaches() == {"warnings": 0, "breaches": 1, "escalations": 1}
    assert notification_types(admin["id"]) == ["sla_escalated"]
    assert check_sla_breaches() == NOTHING


def test_escalation_follows_an_earlier_breach(critical_ticket, shift_due_date):
    shift_due_date(critical_ticket["id"], -1)
    assert check_sla_breaches() == {"warnings": 0, "breaches": 1, "escalations": 0}
    shift_due_date(critical_ticket["id"], -3)
    assert check_sla_breaches() == {"warnings": 0, "breaches": 0, "escalations": 1}


def test_finished_tickets_are_ignored(critical_ticket, set_status, shift_due_date):
    set_status(critical_ticket["id"], "in_progress", "resolved")
    shift_due_date(critical_ticket["id"], -5)
    assert check_sla_breaches() == NOTHING


def test_inactive_agent_is_not_notified(
    client, admin, critical_ticket, agent, customer, shift_due_date, notification_types
):
    client.patch(f"{API}/users/{agent['id']}/deactivate", headers=admin["headers"])
    shift_due_date(critical_ticket["id"], -1)
    check_sla_breaches()
    assert notification_types(agent["id"]) == ["ticket_assigned"]
    assert "sla_breached" in notification_types(customer["id"])