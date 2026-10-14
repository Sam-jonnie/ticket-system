from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "ticket_system",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.sla_tasks", "app.tasks.email_tasks"],)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,  # silences the Celery 6.0 deprecation warning
)

celery_app.conf.beat_schedule = {
    "check-sla-breaches-every-5-minutes": {
        "task": "app.tasks.sla_tasks.check_sla_breaches",
        "schedule": 300.0,
    },
}