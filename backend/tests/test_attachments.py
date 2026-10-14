import uuid
from pathlib import Path

import pytest

from app.core.database import SessionLocal
from app.models.ticket_attachment import TicketAttachment
from app.utils.file_validation import MAX_FILE_SIZE_BYTES

API = "/api/v1"

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
ELF_BYTES = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56  # an executable header, not an image


def error_code(response) -> str:
    return response.json()["error"]["code"]


def upload(client, ticket_id, headers, filename, content, content_type="application/octet-stream"):
    return client.post(
        f"{API}/tickets/{ticket_id}/attachments",
        files={"file": (filename, content, content_type)},
        headers=headers,
    )


def stored_path(attachment_id: str) -> Path:
    with SessionLocal() as db:
        return Path(db.get(TicketAttachment, uuid.UUID(attachment_id)).storage_path)


# ---------- validation ----------

def test_valid_files_are_accepted(client, customer, make_ticket, png_bytes, audit_rows):
    ticket = make_ticket(customer["headers"])
    samples = [
        ("screenshot.png", png_bytes, "image/png"),
        ("invoice.pdf", PDF_BYTES, "application/pdf"),
        ("notes.txt", b"Plain notes about the problem.\n", "text/plain"),
    ]
    for filename, content, expected_type in samples:
        response = upload(client, ticket["id"], customer["headers"], filename, content)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["file_name"] == filename
        assert body["file_type"] == expected_type
        assert body["file_size"] == len(content)
        assert body["uploaded_by"]["id"] == customer["id"]
    assert len(audit_rows("attachment_uploaded")) == 3


def test_file_type_comes_from_content_not_extension(client, customer, make_ticket, png_bytes):
    ticket = make_ticket(customer["headers"])
    png_named_txt = upload(client, ticket["id"], customer["headers"], "picture.txt", png_bytes)
    assert png_named_txt.status_code == 201
    assert png_named_txt.json()["file_type"] == "image/png"

    text_named_exe = upload(
        client, ticket["id"], customer["headers"], "notes.exe", b"Just some plain text notes.\n"
    )
    assert text_named_exe.status_code == 201
    assert text_named_exe.json()["file_type"] == "text/plain"


@pytest.mark.parametrize("content", [ELF_BYTES, bytes(range(256))])
def test_disguised_binaries_are_rejected(client, customer, make_ticket, content):
    ticket = make_ticket(customer["headers"])
    response = upload(
        client, ticket["id"], customer["headers"], "holiday.jpg", content, "image/jpeg"
    )
    assert response.status_code == 400
    assert error_code(response) == "INVALID_ATTACHMENT"
    assert "not allowed" in response.json()["error"]["message"]


def test_empty_and_oversized_files_are_rejected(client, customer, make_ticket):
    ticket = make_ticket(customer["headers"])

    empty = upload(client, ticket["id"], customer["headers"], "empty.txt", b"")
    assert empty.status_code == 400
    assert error_code(empty) == "INVALID_ATTACHMENT"

    huge = upload(
        client, ticket["id"], customer["headers"], "huge.txt", b"a" * (MAX_FILE_SIZE_BYTES + 1)
    )
    assert huge.status_code == 400
    assert error_code(huge) == "INVALID_ATTACHMENT"
    assert "maximum size" in huge.json()["error"]["message"]


# ---------- listing and downloading ----------

def test_list_and_download_round_trip(client, customer, make_ticket, png_bytes):
    ticket = make_ticket(customer["headers"])
    attachment = upload(client, ticket["id"], customer["headers"], "screenshot.png", png_bytes).json()

    listing = client.get(f"{API}/tickets/{ticket['id']}/attachments", headers=customer["headers"])
    assert listing.status_code == 200
    assert [a["file_name"] for a in listing.json()] == ["screenshot.png"]

    download = client.get(
        f"{API}/attachments/{attachment['id']}/download", headers=customer["headers"]
    )
    assert download.status_code == 200
    assert download.content == png_bytes
    assert download.headers["content-type"] == "image/png"
    assert "screenshot.png" in download.headers["content-disposition"]


# ---------- permissions ----------

def test_outsiders_cannot_touch_attachments(client, customer, customer2, make_ticket, png_bytes):
    ticket = make_ticket(customer["headers"])
    attachment = upload(client, ticket["id"], customer["headers"], "a.png", png_bytes).json()

    attempts = [
        upload(client, ticket["id"], customer2["headers"], "b.png", png_bytes),
        client.get(f"{API}/tickets/{ticket['id']}/attachments", headers=customer2["headers"]),
        client.get(f"{API}/attachments/{attachment['id']}/download", headers=customer2["headers"]),
        client.delete(f"{API}/attachments/{attachment['id']}", headers=customer2["headers"]),
    ]
    for response in attempts:
        assert response.status_code == 403
        assert error_code(response) == "TICKET_ACCESS_DENIED"


def test_uploader_can_delete_own_attachment_and_file_is_removed(
    client, customer, make_ticket, png_bytes
):
    ticket = make_ticket(customer["headers"])
    attachment = upload(client, ticket["id"], customer["headers"], "a.png", png_bytes).json()
    path = stored_path(attachment["id"])
    assert path.exists()

    deleted = client.delete(f"{API}/attachments/{attachment['id']}", headers=customer["headers"])
    assert deleted.status_code == 204
    assert not path.exists()


def test_only_uploader_or_admin_can_delete(
    client, admin, customer, agent, make_ticket, assign, png_bytes
):
    ticket = make_ticket(customer["headers"])
    assign(ticket["id"], agent["id"])
    attachment = upload(client, ticket["id"], customer["headers"], "a.png", png_bytes).json()
    path = stored_path(attachment["id"])

    denied = client.delete(f"{API}/attachments/{attachment['id']}", headers=agent["headers"])
    assert denied.status_code == 403
    assert error_code(denied) == "ATTACHMENT_ACCESS_DENIED"
    assert path.exists()

    allowed = client.delete(f"{API}/attachments/{attachment['id']}", headers=admin["headers"])
    assert allowed.status_code == 204
    assert not path.exists()


def test_unknown_attachment_and_missing_authentication(client, customer, make_ticket, png_bytes):
    missing = uuid.uuid4()
    for response in (
        client.get(f"{API}/attachments/{missing}/download", headers=customer["headers"]),
        client.delete(f"{API}/attachments/{missing}", headers=customer["headers"]),
    ):
        assert response.status_code == 404
        assert error_code(response) == "ATTACHMENT_NOT_FOUND"

    ticket = make_ticket(customer["headers"])
    assert upload(client, ticket["id"], {}, "a.png", png_bytes).status_code in (401, 403)