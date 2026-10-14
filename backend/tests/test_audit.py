API = "/api/v1"


def ip_of(row) -> str:
    # Postgres INET may come back as "127.0.0.1" or "127.0.0.1/32" depending on the driver
    return str(row.ip_address).split("/")[0]


def test_logins_are_audited(client, customer, audit_rows):
    ok = client.post(
        f"{API}/auth/login", json={"email": customer["email"], "password": customer["password"]}
    )
    wrong_password = client.post(
        f"{API}/auth/login", json={"email": customer["email"], "password": "WrongPass123!"}
    )
    unknown_email = client.post(
        f"{API}/auth/login", json={"email": "ghost@example.com", "password": "Password123!"}
    )
    assert (ok.status_code, wrong_password.status_code, unknown_email.status_code) == (200, 401, 401)

    logins = audit_rows("login")
    assert len(logins) == 1
    assert str(logins[0].user_id) == customer["id"]
    assert ip_of(logins[0]) == "127.0.0.1"

    # Failed attempts are recorded even though those requests were rejected
    failed = audit_rows("failed_login")
    assert len(failed) == 2
    assert all(row.user_id is None for row in failed)
    assert {row.entity_id for row in failed} == {customer["email"], "ghost@example.com"}
    assert all(ip_of(row) == "127.0.0.1" for row in failed)


def test_self_registration_is_audited(client, audit_rows):
    client.post(
        f"{API}/auth/register",
        json={"name": "New Person", "email": "new@example.com", "password": "Password123!"},
    )
    rows = audit_rows("user_created")
    assert len(rows) == 1
    assert rows[0].metadata_["via"] == "self_registration"
    assert ip_of(rows[0]) == "127.0.0.1"


def test_ticket_lifecycle_is_fully_audited(
    client, admin, agent, customer, make_ticket, assign, set_status, png_bytes, audit_rows
):
    ticket = make_ticket(customer["headers"])
    client.patch(
        f"{API}/tickets/{ticket['id']}",
        json={"title": "Renamed ticket title"},
        headers=customer["headers"],
    )
    assign(ticket["id"], agent["id"])
    client.post(
        f"{API}/tickets/{ticket['id']}/comments",
        json={"message": "Any update?"},
        headers=customer["headers"],
    )
    upload = client.post(
        f"{API}/tickets/{ticket['id']}/attachments",
        files={"file": ("shot.png", png_bytes, "image/png")},
        headers=customer["headers"],
    )
    assert upload.status_code == 201
    set_status(ticket["id"], "in_progress", "resolved", "closed")

    actions = [row.action.value for row in audit_rows()]
    for expected in (
        "ticket_created",
        "ticket_updated",
        "ticket_assigned",
        "comment_added",
        "attachment_uploaded",
        "status_changed",
        "ticket_closed",
    ):
        assert expected in actions, f"missing audit action: {expected}"
    assert actions.count("status_changed") == 3


def test_audit_rows_record_who_what_and_details(client, admin, customer, make_ticket, set_status, audit_rows):
    ticket = make_ticket(customer["headers"])
    set_status(ticket["id"], "in_progress")

    created = audit_rows("ticket_created")[0]
    assert created.entity == "ticket"
    assert created.entity_id == ticket["id"]
    assert str(created.user_id) == customer["id"]
    assert created.metadata_ == {"ticket_number": "TKT-00001", "priority": "high"}

    changed = audit_rows("status_changed")[0]
    assert str(changed.user_id) == admin["id"]
    assert changed.metadata_ == {"old_status": "open", "new_status": "in_progress"}