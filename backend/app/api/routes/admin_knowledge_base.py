"""Admin Knowledge Base Management API.

Lets an admin upload/list/re-index/delete knowledge-base documents through
the UI instead of manually copying files into `backend/knowledgebase/` and
running `scripts/ingest.py`. Shares the same ingestion/indexing logic as that
CLI script (see `app/services/knowledge_base/`), so a document uploaded here
is immediately retrievable by the existing chat RAG pipeline.

Every route requires a valid admin session (see `app/services/auth.py` /
`app/api/routes/admin_auth.py` for the single-account email/password login
that issues that session token).
"""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.auth import require_admin
from app.services.knowledge_base.documents import (
    ValidationError,
    create_document,
    delete_document_record,
    find_by_category_and_filename,
    get_document,
    list_documents,
    mark_failed,
    mark_indexed,
    mark_processing,
    max_upload_bytes,
    resolve_document_path,
    sanitize_category,
    sanitize_filename,
    serialize_document,
    validate_extension,
    compute_stats,
)
from app.services.knowledge_base.ingestion import (
    DocumentExtractionError,
    delete_document_vectors,
    extract_pages,
    index_document,
    split_document,
)

logger = logging.getLogger("app.api.routes.admin_knowledge_base")
router = APIRouter(
    prefix="/api/admin/knowledge-base",
    tags=["admin-knowledge-base"],
    dependencies=[Depends(require_admin)],
)


@router.post("/documents", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(...),
    db: Session = Depends(get_db),
) -> dict:
    logger.info("KB upload started: filename=%s category=%s", file.filename, category)

    try:
        safe_category = sanitize_category(category)
        safe_filename = sanitize_filename(file.filename or "")
        validate_extension(safe_filename)
    except ValidationError as e:
        raise HTTPException(400, str(e)) from e

    content = await file.read()
    if not content:
        raise HTTPException(400, "Uploaded file is empty.")
    if len(content) > max_upload_bytes():
        raise HTTPException(413, f"File exceeds the {settings.kb_max_upload_mb}MB upload limit.")

    if find_by_category_and_filename(db, safe_category, safe_filename):
        raise HTTPException(
            409,
            f"'{safe_filename}' already exists in category '{safe_category}'. "
            "Delete it first or use re-index instead.",
        )

    try:
        dest_path = resolve_document_path(safe_category, safe_filename)
    except ValidationError as e:
        raise HTTPException(400, str(e)) from e

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(content)
    logger.info("KB document saved: %s/%s", safe_category, safe_filename)

    relative_path = f"{safe_category}/{safe_filename}"
    doc = create_document(
        db,
        filename=safe_filename,
        stored_filename=safe_filename,
        category=safe_category,
        relative_path=relative_path,
        file_type=dest_path.suffix.lower().lstrip("."),
        size_bytes=len(content),
    )
    logger.info("KB document registered: id=%s", doc.id)

    try:
        pages = extract_pages(dest_path)
        chunks = split_document(pages)
        if not chunks:
            raise DocumentExtractionError("Document contains no extractable text.")
        chunk_count = index_document(doc.id, doc.filename, doc.category, doc.relative_path, chunks)
    except DocumentExtractionError as e:
        logger.warning("KB indexing failed for document %s (%s): %s", doc.id, relative_path, e)
        mark_failed(db, doc, str(e))
        raise HTTPException(422, f"Document saved but indexing failed: {e}") from e
    except Exception as e:
        logger.error("KB indexing failed unexpectedly for document %s: %s", doc.id, e, exc_info=True)
        mark_failed(db, doc, "Failed to index document due to an internal error.")
        raise HTTPException(500, "Document saved but indexing failed due to an internal error.") from e

    mark_indexed(db, doc, chunk_count)
    logger.info("KB document indexed: id=%s chunks=%d", doc.id, chunk_count)
    return {"document": serialize_document(doc)}


@router.get("/documents")
def get_documents(db: Session = Depends(get_db)) -> dict:
    docs = list_documents(db)
    return {"documents": [serialize_document(d) for d in docs]}


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)) -> dict:
    return compute_stats(db)


@router.delete("/documents/{document_id}")
def delete_document(document_id: str, db: Session = Depends(get_db)) -> dict:
    doc = get_document(db, document_id)
    if not doc:
        raise HTTPException(404, "Unknown document id.")

    try:
        delete_document_vectors(doc.id)
    except Exception as e:
        logger.error("KB delete: failed to remove vectors for %s: %s", doc.id, e, exc_info=True)
        raise HTTPException(500, "Failed to delete document vectors; nothing was removed.") from e

    try:
        file_path = resolve_document_path(doc.category, doc.stored_filename)
    except ValidationError as e:
        # Registry row somehow has an invalid path — still let the admin
        # clear the (now vector-less) record rather than getting stuck.
        logger.error("KB delete: invalid stored path for %s: %s", doc.id, e)
        file_path = None

    if file_path is not None and file_path.exists():
        try:
            file_path.unlink()
        except OSError as e:
            logger.error("KB delete: vectors removed but file delete failed for %s: %s", doc.id, e, exc_info=True)
            raise HTTPException(
                500,
                "Vectors were removed but the file could not be deleted. The document "
                "record was kept so you can retry — contact an administrator if this persists.",
            ) from e
    elif file_path is not None:
        logger.warning("KB delete: file already missing on disk for document %s", doc.id)

    delete_document_record(db, doc)
    logger.info("KB document deleted: id=%s (%s/%s)", doc.id, doc.category, doc.filename)
    return {"deleted": True, "id": doc.id}


@router.post("/documents/{document_id}/reindex")
def reindex_document(document_id: str, db: Session = Depends(get_db)) -> dict:
    doc = get_document(db, document_id)
    if not doc:
        raise HTTPException(404, "Unknown document id.")

    try:
        file_path = resolve_document_path(doc.category, doc.stored_filename)
    except ValidationError as e:
        raise HTTPException(500, str(e)) from e

    if not file_path.exists():
        mark_failed(db, doc, "Source file is missing from disk.")
        raise HTTPException(409, "Cannot re-index: the source file is missing from disk.")

    mark_processing(db, doc)
    logger.info("KB re-index started: id=%s", doc.id)

    try:
        pages = extract_pages(file_path)
        chunks = split_document(pages)
        if not chunks:
            raise DocumentExtractionError("Document contains no extractable text.")
        chunk_count = index_document(doc.id, doc.filename, doc.category, doc.relative_path, chunks)
    except DocumentExtractionError as e:
        logger.warning("KB re-index failed for %s: %s", doc.id, e)
        mark_failed(db, doc, str(e))
        raise HTTPException(422, f"Re-index failed: {e}") from e
    except Exception as e:
        logger.error("KB re-index failed unexpectedly for %s: %s", doc.id, e, exc_info=True)
        mark_failed(db, doc, "Failed to re-index document due to an internal error.")
        raise HTTPException(500, "Re-index failed due to an internal error.") from e

    mark_indexed(db, doc, chunk_count)
    logger.info("KB document re-indexed: id=%s chunks=%d", doc.id, chunk_count)
    return {"document": serialize_document(doc)}
