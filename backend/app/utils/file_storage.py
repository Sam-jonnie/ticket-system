import uuid
from pathlib import Path

UPLOAD_DIR = Path("uploads")


def save_file(file_bytes: bytes, ticket_id: uuid.UUID, original_filename: str) -> str:
    """
    Saves the file under uploads/<ticket_id>/<random-uuid>_<original_name>,
    and returns the relative storage path to persist in the DB.

    The random UUID prefix prevents two uploads with the same filename
    from overwriting each other, while keeping the original name
    visible for readability.
    """
    ticket_dir = UPLOAD_DIR / str(ticket_id)
    ticket_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(original_filename).name  # strips any path components — prevents path traversal
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    full_path = ticket_dir / unique_name

    full_path.write_bytes(file_bytes)
    return str(full_path)


def delete_file(storage_path: str) -> None:
    path = Path(storage_path)
    if path.exists():
        path.unlink()