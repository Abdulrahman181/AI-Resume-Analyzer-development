"""File handling: validation, storage, and text extraction."""

import io
import logging
import os
import uuid
import zipfile

logger = logging.getLogger(__name__)

from fastapi import UploadFile

from app.core import UPLOAD_DIR
from app.exceptions import FileTooLargeError, ValidationError

ALLOWED_EXTENSIONS: set[str] = {"pdf", "docx"}
MAX_FILE_SIZE_MB: int = 5
MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024


def _extension(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    return ext.lstrip(".").lower()


def validate_upload(file: UploadFile) -> str:
    """Return the extension if valid; raise otherwise."""
    if not file.filename:
        raise ValidationError("No filename was provided.")
    ext = _extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Unsupported format '.{ext}'. Upload PDF or DOCX.")
    return ext


def _validate_file_signature(contents: bytes, ext: str) -> None:
    if ext == "pdf":
        if not contents.startswith(b"%PDF-"):
            raise ValidationError("Cannot read PDF — it may be corrupted or unsupported.")
        return
    if ext == "docx":
        if not contents.startswith(b"PK"):
            raise ValidationError("Cannot read DOCX — it may be corrupted or unsupported.")
        try:
            with zipfile.ZipFile(io.BytesIO(contents)) as archive:
                names = set(archive.namelist())
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise ValidationError("Cannot read DOCX — it may be corrupted or unsupported.")
                if archive.testzip() is not None:
                    raise ValidationError("Cannot read DOCX — it may be corrupted or unsupported.")
        except ValidationError:
            raise
        except (OSError, zipfile.BadZipFile):
            raise ValidationError("Cannot read DOCX — it may be corrupted or unsupported.")
        return
    raise ValidationError(f"Unsupported file type: {ext}")


async def save_file(file: UploadFile, ext: str) -> str:
    """Persist a validated upload and return the generated stored path."""
    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise FileTooLargeError(f"Maximum file size is {MAX_FILE_SIZE_MB} MB.")
    if len(contents) == 0:
        raise ValidationError("The uploaded file is empty.")
    _validate_file_signature(contents, ext)

    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}.{ext}"
    with open(dest, "wb") as f:
        f.write(contents)
    return str(dest)


def extract_text(filepath: str, file_type: str) -> str:
    """Route to the appropriate extractor."""
    if file_type == "pdf":
        return _extract_pdf(filepath)
    if file_type == "docx":
        return _extract_docx(filepath)
    raise ValidationError(f"Unsupported file type: {file_type}")


def _extract_pdf(filepath: str) -> str:
    import pdfplumber

    parts: list[str] = []
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    parts.append(text)
    except Exception:
        logger.exception("Resume PDF extraction failed")
        raise ValidationError("Cannot read PDF — it may be corrupted or unsupported.")

    full = "\n".join(parts).strip()
    if not full:
        raise ValidationError("PDF contains no extractable text (possibly scanned).")
    return full


def _extract_docx(filepath: str) -> str:
    from docx import Document

    try:
        doc = Document(filepath)
    except Exception:
        logger.exception("Resume DOCX extraction failed")
        raise ValidationError("Cannot read DOCX — it may be corrupted or unsupported.")

    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    full = "\n".join(parts).strip()
    if not full:
        raise ValidationError("DOCX contains no extractable text.")
    return full
