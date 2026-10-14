"""
Shared test setup.

The environment variables below MUST be set before anything from `app` is
imported, because app.core.config and app.core.database read them at import time.
"""
import os
import struct
import uuid
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url


def _build_test_database_url() -> str:
    """
    Same Postgres as development (host, port, credentials from .env), but a
    separate database whose name ends in _test, so dev data is never touched.
    Set TEST_DATABASE_URL to override completely.
    """
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return explicit

    env_file = Path(__file__).resolve().parent.parent / ".env"
    dev_url = os.getenv("DATABASE_URL") or dotenv_values(env_file).get("DATABASE_URL")
    if not dev_url:
        raise RuntimeError("Set TEST_DATABASE_URL, or DATABASE_URL in backend/.env")

    url = make_url(dev_url)
    name = url.database if url.database.endswith("_test") else f"{url.database}_test"
    return url.set(database=name).render_as_string(hide_password=False)


TEST_DATABASE_URL = _build_test_database_url()
os.environ.update(
    DATABASE_URL=TEST_DATABASE_URL,
    SECRET_KEY="test-secret-key-only-for-automated-tests",
    ENVIRONMENT="testing",
    RATE_LIMIT_ENABLED="false",
    EMAIL_ENABLED="false",
)

os.environ.update(
    DATABASE_URL=TEST_DATABASE_URL,
    SECRET_KEY="test-secret-key-only-for-automated-tests",
    ENVIRONMENT="testing",
    RATE_LIMIT_ENABLED="false",
    EMAIL_ENABLED="false",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app import models  # noqa: E402, F401  (registers every model on Base.metadata)
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.enums import AuditAction, TicketPriority, UserRole  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models.audit_log import AuditLog  # noqa: E402
from app.models.category import Category  # noqa: E402
from app.models.notification import Notification  # noqa: E402
from app.models.priority import Priority  # noqa: E402
from app.models.ticket import Ticket  # noqa: E402
from app.models.user import User  # noqa: E402

API = "/api/v1"
DEFAULT_PASSWORD = "Password123!"
_DEFAULT_HASH = hash_password(DEFAULT_PASSWORD)  # bcrypt is slow, so hash once and reuse

SLA_HOURS = {
    TicketPriority.LOW: 72,
    TicketPriority.MEDIUM: 48,
    TicketPriority.HIGH: 24,
    TicketPriority.CRITICAL: 4,
}


def _ensure_test_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            )
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    # Safety net: this suite TRUNCATES tables, so never let it touch a non-test DB
    assert engine.url.database.endswith("_test"), "Refusing to run on a non-test database"
    _ensure_test_database()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.add_all(Priority(name=n, sla_hours=h) for n, h in SLA_HOURS.items())
        db.commit()
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables():
    """After every test, empty all tables except the seeded priorities."""
    yield
    with engine.begin() as conn:
        # reversed(): delete child tables (tickets, comments...) before their parents (users)
        for table in reversed(Base.metadata.sorted_tables):
            if table.name != "ticket_priorities":
                conn.execute(table.delete())

@pytest.fixture(autouse=True)
def _isolate_side_effects(monkeypatch, tmp_path):
    # No Redis dashboard cache between tests, and uploads go to a temp folder
    monkeypatch.setattr("app.services.dashboard_service.cache_get", lambda key: None)
    monkeypatch.setattr("app.services.dashboard_service.cache_set", lambda *a, **k: None)
    monkeypatch.setattr("app.utils.file_storage.UPLOAD_DIR", tmp_path / "uploads")


class _FakeClientAddress:
    """
    Test-only ASGI wrapper that sets the caller's address to a real IP.
    audit_logs.ip_address is a Postgres INET column, and the test client's
    default fake host "testclient" is not a valid IP address.
    """

    def __init__(self, wrapped_app) -> None:
        self.wrapped_app = wrapped_app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            scope = {**scope, "client": ("127.0.0.1", 50000)}
        await self.wrapped_app(scope, receive, send)


@pytest.fixture
def client():
    with TestClient(_FakeClientAddress(fastapi_app)) as test_client:
        yield test_client

# ---------- users ----------

@pytest.fixture
def make_user():
    def _make(
        role: UserRole = UserRole.CUSTOMER,
        email: str | None = None,
        name: str = "Test User",
        password: str = DEFAULT_PASSWORD,
        is_active: bool = True,
    ) -> dict:
        email = email or f"{role.value}-{uuid.uuid4().hex[:8]}@example.com"
        hashed = _DEFAULT_HASH if password == DEFAULT_PASSWORD else hash_password(password)
        with SessionLocal() as db:
            user = User(
                name=name, email=email, hashed_password=hashed, role=role, is_active=is_active
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            token = create_access_token(user.id, user.role.value)
            return {
                "id": str(user.id),
                "email": email,
                "password": password,
                "token": token,
                "headers": {"Authorization": f"Bearer {token}"},
            }

    return _make


@pytest.fixture
def admin(make_user):
    return make_user(UserRole.ADMIN, name="Admin User")


@pytest.fixture
def agent(make_user):
    return make_user(UserRole.AGENT, name="Agent One")


@pytest.fixture
def agent2(make_user):
    return make_user(UserRole.AGENT, name="Agent Two")


@pytest.fixture
def customer(make_user):
    return make_user(UserRole.CUSTOMER, name="Customer One")


@pytest.fixture
def customer2(make_user):
    return make_user(UserRole.CUSTOMER, name="Customer Two")


# ---------- categories and tickets ----------

def _create_category(name: str, is_active: bool = True) -> dict:
    with SessionLocal() as db:
        cat = Category(name=name, description=f"{name} issues", is_active=is_active)
        db.add(cat)
        db.commit()
        db.refresh(cat)
        return {"id": str(cat.id), "name": cat.name}


@pytest.fixture
def category():
    return _create_category("Technical Support")


@pytest.fixture
def make_category():
    return _create_category


@pytest.fixture
def make_ticket(client, category):
    def _make(
        headers: dict,
        title: str = "Cannot log in to the portal",
        description: str = "I get an error every time I try to log in.",
        priority: str = "high",
        category_id: str | None = None,
    ) -> dict:
        response = client.post(
            f"{API}/tickets",
            json={
                "title": title,
                "description": description,
                "category_id": category_id or category["id"],
                "priority_name": priority,
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture
def set_status(client, admin):
    """Walks a ticket through statuses as admin: set_status(id, 'in_progress', 'resolved')."""

    def _set(ticket_id: str, *statuses: str) -> None:
        for new_status in statuses:
            response = client.patch(
                f"{API}/tickets/{ticket_id}/status",
                json={"status": new_status},
                headers=admin["headers"],
            )
            assert response.status_code == 200, response.text

    return _set


@pytest.fixture
def assign(client, admin):
    def _assign(ticket_id: str, agent_id: str, headers: dict | None = None):
        return client.patch(
            f"{API}/tickets/{ticket_id}/assign",
            json={"agent_id": agent_id},
            headers=headers or admin["headers"],
        )

    return _assign


@pytest.fixture
def shift_due_date():
    """Moves a ticket's due date relative to now (negative hours = overdue)."""

    def _shift(ticket_id: str, hours_from_now: float) -> None:
        with SessionLocal() as db:
            ticket = db.get(Ticket, uuid.UUID(ticket_id))
            ticket.due_date = datetime.now(timezone.utc) + timedelta(hours=hours_from_now)
            db.commit()

    return _shift


# ---------- database inspection helpers ----------

@pytest.fixture
def audit_rows():
    def _get(action: str | None = None) -> list[AuditLog]:
        with SessionLocal() as db:
            query = select(AuditLog).order_by(AuditLog.created_at)
            if action:
                query = query.where(AuditLog.action == AuditAction(action))
            return list(db.scalars(query).all())

    return _get


@pytest.fixture
def notification_types():
    def _get(user_id: str) -> list[str]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(Notification.type).where(Notification.user_id == uuid.UUID(user_id))
            ).all()
            return sorted(r.value for r in rows)

    return _get


@pytest.fixture
def png_bytes() -> bytes:
    """A real, valid 1x1 PNG, so MIME sniffing sees genuine image content."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")