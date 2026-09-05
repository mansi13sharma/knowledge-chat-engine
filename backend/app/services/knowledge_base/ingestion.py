"""Shared document loading / chunking / Chroma indexing for the knowledge base.

Used by both the CLI (`scripts/ingest.py`) and the admin upload/re-index API
routes, so there is exactly one place that knows how to turn a file on disk
into indexed Chroma chunks.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.vectorstore.chroma_client import knowledge_base

logger = logging.getLogger("app.services.knowledge_base.ingestion")

_SPLITTER = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)


class DocumentExtractionError(Exception):
    """A document loader failed to read the file (corrupt/unreadable/unsupported content)."""


class EmptyDocumentError(DocumentExtractionError):
    """The document loaded fine but contained no extractable text."""


@dataclass
class PageText:
    text: str
    # 1-indexed page number for formats that have real pages (PDF). `None`
    # for formats with no native page concept (docx/txt/md) — never invented.
    page: int | None


@dataclass
class Chunk:
    text: str
    page: int | None


def extract_pages(file_path: Path) -> list[PageText]:
    """Load a document's raw text, split per-page where the format has pages.

    Splitting is done per-page (rather than joining everything into one blob
    first, as the original script-only ingestion did) specifically so each
    resulting chunk can be tagged with a single accurate page number.
    """
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".pdf":
            docs = PyPDFLoader(str(file_path)).load()
            # PyPDFLoader's `page` metadata is 0-indexed; store 1-indexed for
            # a human-facing citation ("page 1", not "page 0").
            return [
                PageText(text=d.page_content, page=int(d.metadata.get("page", i)) + 1)
                for i, d in enumerate(docs)
            ]
        if suffix == ".docx":
            text = "\n\n".join(d.page_content for d in Docx2txtLoader(str(file_path)).load())
            return [PageText(text=text, page=None)]
        if suffix in (".txt", ".md"):
            text = TextLoader(str(file_path), encoding="utf-8").load()[0].page_content
            return [PageText(text=text, page=None)]
    except Exception as e:
        raise DocumentExtractionError("Could not extract text from document.") from e

    raise DocumentExtractionError(f"Unsupported file extension '{suffix}'.")


def split_document(pages: list[PageText]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in pages:
        if not page.text.strip():
            continue
        for piece in _SPLITTER.split_text(page.text):
            chunks.append(Chunk(text=piece, page=page.page))
    return chunks


def delete_document_vectors(document_id: str) -> None:
    """Remove every chunk previously indexed for this document_id. Safe to
    call when none exist (e.g. a brand-new document) — Chroma's `where`
    delete is a no-op match rather than an error in that case, which is what
    makes it safe to unconditionally call before every (re-)index."""
    knowledge_base.delete(where={"document_id": document_id})


def index_document(document_id: str, filename: str, category: str, source: str, chunks: list[Chunk]) -> int:
    """(Re-)index one document's chunks under a stable `document_id`.

    Always deletes any existing vectors for this `document_id` first, so
    calling this repeatedly (re-index) never accumulates duplicate vectors —
    there is always exactly one current set of chunks per document.
    """
    delete_document_vectors(document_id)
    if not chunks:
        return 0

    ids = [f"{document_id}::{i}" for i in range(len(chunks))]
    documents = [c.text for c in chunks]
    metadatas = [
        {
            "document_id": document_id,
            "source": source,
            "filename": filename,
            "category": category,
            "chunk": i,
            **({"page": c.page} if c.page is not None else {}),
        }
        for i, c in enumerate(chunks)
    ]
    knowledge_base.add(ids=ids, documents=documents, metadatas=metadatas)
    logger.info("Indexed %d chunk(s) for document_id=%s (%s)", len(chunks), document_id, source)
    return len(chunks)


def load_and_index(file_path: Path, document_id: str, filename: str, category: str, source: str) -> int:
    """Extract + chunk + index a file in one call. Raises `EmptyDocumentError`
    if the document has no extractable text, or `DocumentExtractionError` if
    the loader itself failed — callers should catch both."""
    pages = extract_pages(file_path)
    chunks = split_document(pages)
    if not chunks:
        raise EmptyDocumentError("Document contains no extractable text.")
    return index_document(document_id, filename, category, source, chunks)
