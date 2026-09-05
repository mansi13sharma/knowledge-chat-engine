"""Tests for the admin knowledge-base upload/list/reindex/delete API and the
shared ingestion service it's built on."""

import io
import uuid

import pytest

from app.core.config import settings
from app.services.knowledge_base import documents as kb_documents
from app.services.knowledge_base.ingestion import Chunk, delete_document_vectors, index_document
from app.services.vectorstore.chroma_client import knowledge_base, query_collection

BASE = "/api/admin/knowledge-base"


def _upload(client, filename: str, content: bytes, category: str = "nodejs", content_type: str = "text/plain"):
    return client.post(
        f"{BASE}/documents",
        files={"file": (filename, io.BytesIO(content), content_type)},
        data={"category": category},
    )


# --- upload validation -----------------------------------------------------


def test_upload_supported_document_indexes_successfully(client):
    resp = _upload(client, "guide.txt", b"Node.js is a JavaScript runtime. " * 50)
    assert resp.status_code == 201
    doc = resp.json()["document"]
    assert doc["filename"] == "guide.txt"
    assert doc["category"] == "nodejs"
    assert doc["file_type"] == "txt"
    assert doc["status"] == "indexed"
    assert doc["chunks"] > 0


def test_upload_unsupported_extension_rejected(client):
    resp = _upload(client, "malware.exe", b"binary-ish content")
    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]


def test_upload_empty_file_rejected(client):
    resp = _upload(client, "empty.txt", b"")
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_upload_oversized_file_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "kb_max_upload_mb", 0)  # 0 MB -> anything is "too large"
    resp = _upload(client, "guide.txt", b"just a few bytes")
    assert resp.status_code == 413
    assert "limit" in resp.json()["detail"].lower()


def test_upload_whitespace_only_document_marked_failed(client):
    resp = _upload(client, "blank.txt", b"   \n\n\t  \n")
    assert resp.status_code == 422

    listing = client.get(f"{BASE}/documents").json()["documents"]
    assert len(listing) == 1
    assert listing[0]["status"] == "failed"
    assert listing[0]["error_message"]


def test_upload_duplicate_category_and_filename_rejected(client):
    first = _upload(client, "guide.txt", b"content one " * 20)
    assert first.status_code == 201

    second = _upload(client, "guide.txt", b"content two " * 20)
    assert second.status_code == 409


def test_upload_sanitizes_category_and_filename_path_traversal(client):
    resp = client.post(
        f"{BASE}/documents",
        files={"file": ("../../../etc/passwd", io.BytesIO(b"some content"), "text/plain")},
        data={"category": "../../etc"},
    )
    # After stripping path separators the "filename" has no recognized
    # extension left, so it's rejected as unsupported rather than ever
    # touching the filesystem outside the knowledge-base directory.
    assert resp.status_code == 400


def test_upload_sanitizes_category_with_valid_extension(client):
    resp = _upload(client, "guide.txt", b"safe content " * 20, category="../../etc/passwd")
    assert resp.status_code == 201
    category = resp.json()["document"]["category"]
    assert "/" not in category
    assert ".." not in category

    kb_dir = settings.kb_data_dir
    from pathlib import Path

    resolved_root = Path(kb_dir).resolve()
    for path in resolved_root.rglob("*"):
        if path.is_file():
            assert resolved_root in path.resolve().parents


# --- metadata / dedup / delete ----------------------------------------------


def test_metadata_stored_in_chroma(client):
    resp = _upload(client, "guide.txt", b"Node.js is great. " * 40)
    doc_id = resp.json()["document"]["id"]

    result = knowledge_base.get(where={"document_id": doc_id})
    assert len(result["ids"]) == resp.json()["document"]["chunks"]
    for metadata in result["metadatas"]:
        assert metadata["document_id"] == doc_id
        assert metadata["filename"] == "guide.txt"
        assert metadata["category"] == "nodejs"
        assert "chunk" in metadata
        # .txt has no native page concept — must not be invented.
        assert "page" not in metadata


def test_index_document_includes_page_metadata_only_when_present():
    document_id = uuid.uuid4().hex
    chunks = [Chunk(text="page one text", page=3), Chunk(text="no page info", page=None)]
    count = index_document(document_id, "f.pdf", "cat", "cat/f.pdf", chunks)
    assert count == 2

    result = knowledge_base.get(where={"document_id": document_id})
    by_text = {m["chunk"]: m for m in result["metadatas"]}
    assert by_text[0]["page"] == 3
    assert "page" not in by_text[1]

    delete_document_vectors(document_id)
    assert knowledge_base.get(where={"document_id": document_id})["ids"] == []


def test_delete_document_vectors_is_idempotent_when_none_exist():
    delete_document_vectors(uuid.uuid4().hex)  # must not raise


def test_reindex_does_not_duplicate_vectors(client):
    resp = _upload(client, "guide.txt", b"Node.js runtime docs. " * 40)
    doc = resp.json()["document"]
    doc_id, original_chunks = doc["id"], doc["chunks"]

    for _ in range(3):
        reindex_resp = client.post(f"{BASE}/documents/{doc_id}/reindex")
        assert reindex_resp.status_code == 200
        assert reindex_resp.json()["document"]["chunks"] == original_chunks

        vector_ids = knowledge_base.get(where={"document_id": doc_id})["ids"]
        assert len(vector_ids) == original_chunks  # never duplicated


def test_delete_removes_vectors_for_only_that_document(client):
    doc_a = _upload(client, "a.txt", b"Document A content. " * 30, category="cat-a").json()["document"]
    doc_b = _upload(client, "b.txt", b"Document B content. " * 30, category="cat-b").json()["document"]

    resp = client.delete(f"{BASE}/documents/{doc_a['id']}")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True, "id": doc_a["id"]}

    assert knowledge_base.get(where={"document_id": doc_a["id"]})["ids"] == []
    assert len(knowledge_base.get(where={"document_id": doc_b["id"]})["ids"]) == doc_b["chunks"]

    from pathlib import Path

    assert not (Path(settings.kb_data_dir) / "cat-a" / "a.txt").exists()
    assert (Path(settings.kb_data_dir) / "cat-b" / "b.txt").exists()

    listing_ids = {d["id"] for d in client.get(f"{BASE}/documents").json()["documents"]}
    assert doc_a["id"] not in listing_ids
    assert doc_b["id"] in listing_ids


# --- listing / stats / not-found --------------------------------------------


def test_empty_knowledge_base_returns_zero_stats_and_empty_list(client):
    assert client.get(f"{BASE}/documents").json() == {"documents": []}
    assert client.get(f"{BASE}/stats").json() == {
        "total_documents": 0,
        "total_chunks": 0,
        "categories": 0,
        "per_category": {},
    }


def test_query_collection_handles_empty_collection():
    assert query_collection(knowledge_base, "anything", 5) == []


def test_list_documents_returns_all(client):
    _upload(client, "a.txt", b"Document A. " * 30, category="cat-a")
    _upload(client, "b.txt", b"Document B. " * 30, category="cat-b")

    listing = client.get(f"{BASE}/documents").json()["documents"]
    assert {d["filename"] for d in listing} == {"a.txt", "b.txt"}
    for d in listing:
        assert d["status"] == "indexed"
        assert "stored_filename" not in d
        assert "relative_path" not in d


def test_stats_calculation(client):
    _upload(client, "a.txt", b"Document A content here. " * 30, category="cat-a")
    _upload(client, "b.txt", b"Document B content here. " * 30, category="cat-b")

    stats = client.get(f"{BASE}/stats").json()
    assert stats["total_documents"] == 2
    assert stats["categories"] == 2
    assert stats["per_category"] == {"cat-a": 1, "cat-b": 1}
    assert stats["total_chunks"] > 0


@pytest.mark.parametrize("method,path_suffix", [("delete", ""), ("post", "/reindex")])
def test_unknown_document_id_returns_404(client, method, path_suffix):
    fake_id = uuid.uuid4().hex
    resp = getattr(client, method)(f"{BASE}/documents/{fake_id}{path_suffix}")
    assert resp.status_code == 404


def test_reindex_missing_file_marks_failed(client):
    resp = _upload(client, "guide.txt", b"Node.js runtime docs. " * 30)
    doc = resp.json()["document"]

    from pathlib import Path

    (Path(settings.kb_data_dir) / doc["category"] / doc["filename"]).unlink()

    reindex_resp = client.post(f"{BASE}/documents/{doc['id']}/reindex")
    assert reindex_resp.status_code == 409

    listing = client.get(f"{BASE}/documents").json()["documents"]
    assert next(d for d in listing if d["id"] == doc["id"])["status"] == "failed"


def test_sanitize_category_rejects_all_stripped_input():
    with pytest.raises(kb_documents.ValidationError):
        kb_documents.sanitize_category("../../")


def test_sanitize_filename_strips_directory_components():
    assert kb_documents.sanitize_filename("../../etc/passwd.txt") == "passwd.txt"
