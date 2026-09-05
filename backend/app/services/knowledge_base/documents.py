"""Filesystem safety, name sanitization, and the `KnowledgeDocument` registry
CRUD used by the admin knowledge-base API (and indirectly by the CLI, which
shares the sanitized-category convention via `sanitize_category`).
"""

import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import KnowledgeDocument

# Only these are accepted for upload/ingestion — reject everything else up
# front rather than letting an unknown suffix reach a document loader.
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

_CATEGORY_CLEAN_RE = re.compile(r"[^a-z0-9_-]")
_FILENAME_CLEAN_RE = re.compile(r"[^A-Za-z0-9._-]")


class ValidationError(ValueError):
    """A user-fixable input problem (bad category/filename/extension/size)."""


def sanitize_category(raw: str) -> str:
    """Normalize a user-supplied category into a safe folder name.

    Lowercases, replaces whitespace with '-', strips anything that isn't
    alphanumeric/'-'/'_' — which also strips path separators and '..' segments,
    so a value like "../../etc" collapses to "etcetc"/"etc" rather than ever
    reaching the filesystem as a traversal.
    """
    normalized = (raw or "").strip().lower().replace(" ", "-")
    normalized = _CATEGORY_CLEAN_RE.sub("", normalized)
    normalized = normalized.strip("-_")
    if not normalized:
        raise ValidationError("Category must contain at least one letter, number, '-' or '_'.")
    return normalized[:60]


def sanitize_filename(raw: str) -> str:
    """Normalize a user-supplied filename into a safe on-disk filename.

    `Path(raw).name` alone discards any directory components (so
    "../../x/evil.pdf" becomes "evil.pdf"); the character filter then removes
    anything else that isn't a conservative filename character.
    """
    name = Path((raw or "").strip()).name
    name = _FILENAME_CLEAN_RE.sub("_", name)
    name = name.lstrip(".")  # no hidden dotfiles, no bare ".."/"."
    if not name:
        raise ValidationError("Filename is invalid or empty.")
    return name[:200]


def validate_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValidationError(f"Unsupported file type '{ext or '(none)'}'. Allowed types: {allowed}.")
    return ext


def resolve_document_path(category: str, stored_filename: str) -> Path:
    """Resolve where a (category, filename) pair lives on disk, refusing to
    resolve outside `kb_data_dir` even if sanitization above were somehow
    bypassed — a defense-in-depth check, not the primary guard."""
    base = Path(settings.kb_data_dir).resolve()
    candidate = (base / category / stored_filename).resolve()
    if candidate != base and base not in candidate.parents:
        raise ValidationError("Resolved document path escapes the knowledge-base directory.")
    return candidate


def max_upload_bytes() -> int:
    return settings.kb_max_upload_mb * 1024 * 1024


# --- KnowledgeDocument registry -------------------------------------------------


def get_document(db: Session, document_id: str) -> KnowledgeDocument | None:
    return db.get(KnowledgeDocument, document_id)


def find_by_category_and_filename(db: Session, category: str, filename: str) -> KnowledgeDocument | None:
    stmt = select(KnowledgeDocument).where(
        KnowledgeDocument.category == category, KnowledgeDocument.filename == filename
    )
    return db.scalars(stmt).first()


def list_documents(db: Session) -> list[KnowledgeDocument]:
    stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.updated_at.desc())
    return list(db.scalars(stmt).all())


def create_document(
    db: Session,
    *,
    filename: str,
    stored_filename: str,
    category: str,
    relative_path: str,
    file_type: str,
    size_bytes: int,
) -> KnowledgeDocument:
    doc = KnowledgeDocument(
        filename=filename,
        stored_filename=stored_filename,
        category=category,
        relative_path=relative_path,
        file_type=file_type,
        size_bytes=size_bytes,
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def mark_processing(db: Session, doc: KnowledgeDocument) -> None:
    doc.status = "processing"
    doc.error_message = None
    db.commit()


def mark_indexed(db: Session, doc: KnowledgeDocument, chunk_count: int) -> None:
    doc.status = "indexed"
    doc.chunk_count = chunk_count
    doc.error_message = None
    db.commit()
    db.refresh(doc)


def mark_failed(db: Session, doc: KnowledgeDocument, error_message: str) -> None:
    doc.status = "failed"
    doc.error_message = error_message[:500]
    db.commit()


def delete_document_record(db: Session, doc: KnowledgeDocument) -> None:
    db.delete(doc)
    db.commit()


def compute_stats(db: Session) -> dict:
    """Stats reflect only currently-`indexed` documents — a `failed` row has
    no live vectors, so counting it would over-report what's actually
    searchable."""
    stmt = select(KnowledgeDocument).where(KnowledgeDocument.status == "indexed")
    indexed = list(db.scalars(stmt).all())

    per_category: dict[str, int] = {}
    for doc in indexed:
        per_category[doc.category] = per_category.get(doc.category, 0) + 1

    return {
        "total_documents": len(indexed),
        "total_chunks": sum(doc.chunk_count for doc in indexed),
        "categories": len(per_category),
        "per_category": per_category,
    }


def serialize_document(doc: KnowledgeDocument) -> dict:
    """Frontend-facing shape — deliberately omits `stored_filename` and
    `relative_path` so no filesystem path (even a relative one) leaks out."""
    return {
        "id": doc.id,
        "filename": doc.filename,
        "category": doc.category,
        "file_type": doc.file_type,
        "size": doc.size_bytes,
        "chunks": doc.chunk_count,
        "status": doc.status,
        "updated_at": doc.updated_at.isoformat(),
        "created_at": doc.created_at.isoformat(),
        "error_message": doc.error_message,
    }
