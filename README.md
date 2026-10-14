# Support Ticket Management System - Backend

A secure, layered REST API for a support-ticket system: customers raise tickets, agents work them, admins manage everything. Built with **FastAPI, SQLAlchemy 2.0, PostgreSQL, Alembic, Redis and Celery**.

## Features

- **Authentication**: JWT access tokens + rotating refresh tokens stored server-side, logout (revocation), change password, bcrypt hashing, inactive users cannot log in
- **Authorization**: role-based (Admin / Agent / Customer) **and** resource-based (customers see only their tickets, agents only tickets assigned to them)
- **Tickets**: CRUD, ticket numbers (`TKT-00001`), status workflow with validated transitions, assignment with history, pagination / search / sorting / 6 filters, CSV export
- **SLA**: due date from priority (Low 72h, Medium 48h, High 24h, Critical 4h), overdue detection, 3-stage escalation
- **Comments** (own-edit, admin moderation), **attachments** (content-based MIME validation, size limit)
- **Notifications**: in-app (REST + WebSocket) and email, 8 event types
- **Dashboard** statistics per role, **audit log** (read-only for admins)
- **Bonus**: Redis, Celery + Beat, WebSocket, email (Mailpit), Docker + Compose, Redis caching, rate limiting, API versioning (`/api/v1`), advanced SLA escalation, CSV export

## Tech stack

| Area | Choice |
|---|---|
| Framework | FastAPI, Pydantic v2 (`ConfigDict`, `pydantic-settings` with `SettingsConfigDict`) |
| Database | PostgreSQL 16, SQLAlchemy 2.0 (`Mapped`, `mapped_column`), Alembic, `psycopg` v3 |
| Auth | python-jose (JWT), bcrypt |
| Background work | FastAPI `BackgroundTasks`, Celery + Celery Beat, Redis |
| Protection | SlowAPI rate limiting (Redis-backed) |
| Email | SMTP; Mailpit as the development inbox |
| Tests | pytest, httpx / Starlette TestClient |
| Runtime | Docker, Docker Compose |

## Architecture

```
Routes -> Dependencies -> Services -> Repositories -> Models -> Database
```

Routes only translate HTTP; services hold all business rules; repositories hold SQL. Diagrams: [docs/architecture.md](docs/architecture.md) and the [ER diagram](docs/er-diagram.md).

```
backend/
  app/
    core/          config, database, enums, security (JWT, hashing), deps (auth, roles),
                   exceptions (central handlers), cache, rate limit, Celery app, WebSocket manager
    models/        SQLAlchemy models
    schemas/       Pydantic request/response models
    repositories/  database queries
    services/      business logic
    routes/        API routers
    tasks/         Celery tasks (SLA checks, email)
    utils/         ticket numbers, SLA maths, file validation, file storage, email
  alembic/         migrations
  scripts/         seed_demo.py, seed_admin.py, seed_priorities.py, generate_postman.py
  tests/           pytest suite
  postman/         generated Postman collection
  docs/            ER and architecture diagrams
```

## Quick start (Docker)

Requires Docker Desktop.

```bash
cd backend
cp .env.example .env            # Windows PowerShell: copy .env.example .env
# put a real secret in .env:  python -c "import secrets; print(secrets.token_urlsafe(32))"

docker compose up -d --build
docker compose exec api python scripts/seed_demo.py
```

| What | URL |
|---|---|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Mailpit (sent emails) | http://localhost:8025 |
| PostgreSQL (from your machine) | `localhost:5436` (user `ticket_user`, db `ticket_system`) |

Compose starts PostgreSQL, Redis, Mailpit, a one-shot `migrate` job (`alembic upgrade head`), the API, a Celery worker and Celery Beat.

## Local development (API on your machine)

```bash
cd backend
docker compose up -d postgres redis mailpit     # infrastructure only
python -m venv venv
venv\Scripts\activate                           # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                            # then set SECRET_KEY
alembic upgrade head
python scripts/seed_demo.py
uvicorn app.main:app --reload
# separate terminals:
celery -A app.core.celery_app worker --loglevel=info --pool=solo   # --pool=solo is for Windows
celery -A app.core.celery_app beat --loglevel=info
```

## Configuration

All settings come from environment variables or `.env` (see `.env.example`).

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy URL (`postgresql+psycopg://...`) | required |
| `SECRET_KEY` | JWT signing key | required |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | access token lifetime | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | refresh token lifetime | `7` |
| `ENVIRONMENT` | `development` also echoes SQL | `development` |
| `REDIS_URL` | Celery broker, rate limits, cache | `redis://localhost:6379/0` |
| `RATE_LIMIT_ENABLED` | toggle rate limiting | `true` |
| `EMAIL_ENABLED` | toggle email sending | `false` |
| `EMAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS` | SMTP settings | Mailpit-friendly |

## Seeding and credentials

`python scripts/seed_demo.py` (inside Docker: `docker compose exec api python scripts/seed_demo.py`) is idempotent and creates the 4 priorities with their SLA hours, the 5 categories from the brief (Technical Support, Billing, Account, Product Issue, General) and these **demo-only** users:

| Role | Email | Password |
|---|---|---|
| Admin | admin@example.com | Admin@12345 |
| Agent | agent1@example.com, agent2@example.com | Agent@12345 |
| Customer | customer1@example.com, customer2@example.com | Customer@12345 |

Public registration always creates a **customer**. Admins and agents are created by an admin (`POST /api/v1/users`) or by the seed script.

## Testing with Swagger

1. Open http://localhost:8000/docs.
2. `POST /api/v1/auth/login` with the **customer** credentials, copy `access_token`.
3. Click **Authorize** (top right), paste the token (just the token, no `Bearer `), click Authorize.
4. `GET /api/v1/categories` and copy a category `id`.
5. `POST /api/v1/tickets` with that `category_id` and a `priority_name`. Note `ticket_number`, `due_date` and `priority.sla_hours` in the response. Copy the ticket `id`.
6. Switch role: Authorize, Logout, log in as **admin**, authorize with the new token.
7. `GET /api/v1/users?role=agent`, copy an agent `id`, then `PATCH /api/v1/tickets/{id}/assign`.
8. Log in as that **agent**: `PATCH /tickets/{id}/status` with `in_progress`, then try `closed` to see the `INVALID_STATUS_TRANSITION` error, then `resolved`.
9. As the agent or customer: `POST /tickets/{id}/comments`, and upload a PNG/PDF with `POST /tickets/{id}/attachments`. Try uploading a renamed `.exe` to see content-based validation reject it.
10. As admin: `PATCH /tickets/{id}/status` to `closed`, then try to comment (rejected: closed tickets are locked).
11. Check `GET /notifications` for each user, `GET /dashboard/stats`, `GET /audit-logs` (admin only) and `GET /tickets/export` (CSV).
12. Open Mailpit (http://localhost:8025) to see the emails.
13. Rate limiting: send 6 wrong-password logins in a minute; the 6th returns `429`.

To test SLA escalation without waiting, back-date a ticket and run the job:

```bash
docker compose exec postgres psql -U ticket_user -d ticket_system -c "UPDATE tickets SET due_date = NOW() - INTERVAL '3 hours' WHERE ticket_number = 'TKT-00001';"
docker compose exec api python -c "from app.tasks.sla_tasks import check_sla_breaches; print(check_sla_breaches())"
```

Live notifications: connect a WebSocket client to `ws://localhost:8000/ws/notifications?token=<access_token>`.

## API overview

All endpoints are under `/api/v1` unless noted. Interactive docs: `/docs`. A ready-made [Postman collection](postman/ticket_system.postman_collection.json) covers every endpoint (import it, run a `Login` request, then call anything).

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/auth/register` | public | Register (customer) |
| POST | `/auth/login` | public | Login (5/min per IP) |
| POST | `/auth/refresh` | public | Rotate refresh token |
| POST | `/auth/logout` | any | Revoke refresh token |
| GET | `/auth/me` | any | Current user |
| POST | `/auth/change-password` | any | Change password |
| POST, GET | `/users` | admin | Create, list (page, page_size, role) |
| GET, PATCH | `/users/{id}` | admin | Get, update |
| PATCH | `/users/{id}/activate`, `/deactivate`, `/role` | admin | Status and role |
| POST | `/categories` | admin | Create |
| GET | `/categories` | any | List (`active_only`) |
| PATCH | `/categories/{id}`, `/activate`, `/deactivate` | admin | Manage |
| POST, GET | `/tickets` | any | Create, list/search/filter/sort/paginate |
| GET | `/tickets/export` | any | CSV (same filters, role-scoped) |
| GET, PATCH | `/tickets/{id}` | owner / assigned / admin | Get, update |
| PATCH | `/tickets/{id}/status` | agent, admin | Change status |
| PATCH | `/tickets/{id}/assign` | agent, admin | Assign / reassign |
| DELETE | `/tickets/{id}` | admin | Delete |
| POST, GET | `/tickets/{id}/comments` | participants | Add, list |
| PATCH, DELETE | `/comments/{id}` | author / admin | Edit, delete |
| POST, GET | `/tickets/{id}/attachments` | participants | Upload, list |
| GET, DELETE | `/attachments/{id}/download`, `/attachments/{id}` | participants / uploader or admin | Download, delete |
| GET | `/notifications` | any | List (`unread_only`) |
| PATCH | `/notifications/{id}/read`, `/notifications/read-all` | any | Mark read |
| GET | `/dashboard/stats` | any | Ticket stats scoped by role |
| GET | `/dashboard/admin`, `/dashboard/agent` | admin / agent | Role-specific stats |
| GET | `/audit-logs` | admin | Read-only audit trail with filters |
| GET | `/health` (no prefix) | public | Liveness |
| WS | `/ws/notifications?token=` (no prefix) | any | Live notifications |

Ticket list filters: `status`, `priority`, `category_id`, `assigned_agent`, `customer`, `date_from`, `date_to`, plus `search` (title/description), `sort_by` (`created_at`, `updated_at`, `due_date`, `title`, `status`), `sort_order`, `page`, `page_size`.

## Request and response examples

**Register** - `POST /api/v1/auth/register`

```json
{ "name": "Jane Customer", "email": "jane@example.com", "password": "Password123!" }
```
```json
{
  "id": "5b1d6c0e-0f7e-4a38-9e0d-6b3c1c0c8f11",
  "name": "Jane Customer",
  "email": "jane@example.com",
  "role": "customer",
  "is_active": true,
  "created_at": "2026-10-14T09:00:00Z",
  "updated_at": "2026-10-14T09:00:00Z"
}
```

**Login** - `POST /api/v1/auth/login`

```json
{ "email": "customer1@example.com", "password": "Customer@12345" }
```
```json
{ "access_token": "eyJhbGciOi...", "refresh_token": "eyJhbGciOi...", "token_type": "bearer" }
```

**Create ticket** - `POST /api/v1/tickets`

```json
{
  "title": "Cannot log in to the portal",
  "description": "I get an error every time I try to log in.",
  "category_id": "0c0b8f3e-6b0a-4c55-8b69-1c2f6d1b9a10",
  "priority_name": "high"
}
```
```json
{
  "id": "f3a0c2d4-2a5c-4a38-8d0f-0a8d3e2f7b21",
  "ticket_number": "TKT-00001",
  "title": "Cannot log in to the portal",
  "status": "open",
  "customer": { "id": "...", "name": "Customer One", "email": "customer1@example.com" },
  "assigned_agent": null,
  "category": { "id": "...", "name": "Technical Support" },
  "priority": { "id": "...", "name": "high", "sla_hours": 24 },
  "due_date": "2026-10-15T09:00:00Z",
  "created_at": "2026-10-14T09:00:00Z",
  "updated_at": "2026-10-14T09:00:00Z"
}
```

**List tickets** - `GET /api/v1/tickets?status=open&priority=high&search=login&page=1&page_size=20`

```json
{ "items": [ { "ticket_number": "TKT-00001", "...": "..." } ], "total": 1, "page": 1, "page_size": 20 }
```

**Errors** use one shape everywhere:

```json
{ "success": false, "error": { "code": "INVALID_STATUS_TRANSITION", "message": "Cannot move ticket from open to closed" } }
```
```json
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "Request validation failed", "details": [ { "loc": ["body", "title"], "msg": "String should have at least 5 characters" } ] } }
```

Handled statuses: 400, 401, 403, 404, 405, 409, 422, 429 (`RATE_LIMIT_EXCEEDED`) and 500 (`INTERNAL_SERVER_ERROR`).

## Permissions

| Action | Customer | Agent | Admin |
|---|---|---|---|
| Create ticket | yes | yes | yes |
| View / list tickets | own | assigned to them | all |
| Edit ticket fields (until closed) | own | assigned | all |
| Change status | no | assigned | all |
| Assign / reassign | no | yes | yes |
| Delete ticket | no | no | yes |
| Comment | own tickets | assigned | all |
| Edit / delete a comment | own | own | any (moderation) |
| Upload / download attachments | own tickets | assigned | all |
| Delete attachment | own uploads | own uploads | any |
| Manage users and categories | no | no | yes |
| Audit logs | no | no | read-only |

## Business rules

**Status workflow.** `open -> in_progress -> resolved -> closed`. `in_progress` can go back to `open`, and `resolved` can be reopened to `in_progress`. `closed` is final. Anything else returns `INVALID_STATUS_TRANSITION`. Closed tickets cannot be edited or commented on.

**Assignment.** Customers cannot assign. Only active users with the agent role can receive tickets. Every assignment and status change is stored in `ticket_status_history`, and the new assignee is notified.

**SLA.** `due_date = created_at + priority SLA`; changing the priority recalculates it. A scheduled Celery job (every 5 minutes) checks open tickets:

| Stage | Trigger | Notified |
|---|---|---|
| Warning | 80% of the SLA window used | assigned agent (admins if unassigned) |
| Breach | due date passed | customer and assigned agent |
| Escalation | overdue by 50% of the SLA window | all active admins |

Each stage fires once per ticket.

**Attachments.** Allowed: JPEG, PNG, GIF, PDF, plain text, DOC/DOCX, ZIP, max 10 MB. The type is detected from the file **content** (libmagic), never trusted from the extension or the client's `Content-Type`. Stored names get a random prefix and path components are stripped.

**Audit log.** Recorded for login, failed login, user created/updated, ticket created/updated/assigned/status changed/closed, comment added, attachment uploaded: with user, action, entity, entity id, timestamp, IP and metadata. The audit row is written in the same transaction as the action (failed logins are committed even though the request is rejected). The only audit endpoint is a read.

## Automated tests

```bash
cd backend
pytest                                           # 130+ tests
pytest --cov=app --cov-report=term-missing       # needs: pip install pytest-cov
docker compose exec api pytest                   # or run inside the container
```

Tests use a separate `<database>_test` database on the same server, created automatically and truncated between tests, so development data is never touched. Redis caching and e-mail are disabled during tests. Coverage includes registration, login, token validation (expired, forged, wrong token type), authorization, user management, ticket CRUD, assignment, status transitions, comments, attachments, notifications (including WebSocket auth), dashboard, SLA calculation and the Celery SLA job, audit logs, and negative cases for invalid credentials, unauthorized access, invalid transitions, inactive-agent assignment, duplicate email, comment tampering, invalid uploads and invalid categories.

## Design decisions and known limitations

- **Roles are a Postgres enum column**, not a `roles` table. There are exactly three fixed roles, and an enum gives database-level validation with no extra join. A table would be the next step if roles became configurable.
- **Ticket numbers** use `COUNT + 1`. Two simultaneous creations could collide; the unique constraint turns that into an error, never bad data. A Postgres `SEQUENCE` would remove the race.
- **Dashboard caching** uses a 60-second TTL in Redis, so numbers can be up to a minute stale. If Redis is down, requests fall back to the database.
- **WebSocket push** works for notifications created by the API process. SLA notifications are created by the Celery worker, a separate process, so they reach users through REST and email. Redis pub/sub between the two would close that gap.
- **Attachments are stored on local disk** (a Docker volume). Object storage (S3) would be used in production, along with virus scanning.
- **CSV export** is built in memory and capped at 5,000 rows; cells starting with `= + - @` are neutralised against spreadsheet formula injection.
- **Rate limiting** is per client IP; behind a reverse proxy it would need to read `X-Forwarded-For`.
- **Refresh tokens** are stored as issued; hashing them at rest would be a good hardening step.
- Passwords require 8-128 characters; no complexity rules are enforced.

**Author**
- Samuel Jonathan R,
- Python Full Stack Developer,
- Stackly