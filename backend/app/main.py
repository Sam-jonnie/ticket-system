from fastapi import FastAPI

from slowapi.middleware import SlowAPIMiddleware
from app.core.rate_limit import limiter

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.routes import auth, users, categories, tickets, comments, attachments, notifications, ws_notifications, dashboard, audit_logs


app = FastAPI(
    title="Support Ticket Management System",
    version="1.0.0",
    description="Backend API for ticket creation, assignment, SLA tracking and notifications.",
)

register_exception_handlers(app)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

API_V1_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_V1_PREFIX)
app.include_router(users.router, prefix=API_V1_PREFIX)
app.include_router(categories.router, prefix=API_V1_PREFIX)
app.include_router(tickets.router, prefix=API_V1_PREFIX)
app.include_router(comments.router, prefix=API_V1_PREFIX)
app.include_router(attachments.router, prefix=API_V1_PREFIX)
app.include_router(notifications.router, prefix=API_V1_PREFIX)
app.include_router(ws_notifications.router)
app.include_router(dashboard.router, prefix=API_V1_PREFIX)
app.include_router(audit_logs.router, prefix=API_V1_PREFIX)

@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}