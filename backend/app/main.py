from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(
    title="Support Ticket Management System",
    version="1.0.0",
    description="Backend API for ticket creation, assignment, SLA tracking and notifications.",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}