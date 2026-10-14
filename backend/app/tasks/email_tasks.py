from app.core.celery_app import celery_app
from app.utils.email import send_email_smtp


@celery_app.task(
    name="app.tasks.email_tasks.send_email_task",
    autoretry_for=(OSError,),            # SMTP/connection errors are OSError subclasses
    retry_backoff=True,                  # waits 1s, 2s, 4s... between retries
    retry_kwargs={"max_retries": 3},
)
def send_email_task(to_email: str, subject: str, body: str) -> None:
    send_email_smtp(to_email, subject, body)