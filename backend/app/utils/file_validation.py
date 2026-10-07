import magic

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "application/pdf",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/zip",
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def detect_mime_type(file_bytes: bytes) -> str:
    return magic.from_buffer(file_bytes, mime=True)


def validate_attachment(file_bytes: bytes, declared_filename: str) -> str:
    if len(file_bytes) == 0:
        raise ValueError("Uploaded file is empty")
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES} bytes")

    detected_type = detect_mime_type(file_bytes)
    if detected_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"File type '{detected_type}' is not allowed")

    return detected_type