"""Ingest FAQ or knowledge-base content into their respective Chroma collections.

Usage:
    python -m scripts.ingest --collection knowledge_base --path ./knowledgebase
    python -m scripts.ingest --collection faq             --path ./faq
    python -m scripts.ingest --collection knowledge_base --path ./knowledgebase --reset
"""

import argparse
import json
import sys
import uuid
from pathlib import Path

from app.services.knowledge_base.documents import ALLOWED_EXTENSIONS as KB_SUFFIXES
from app.services.knowledge_base.ingestion import (
    DocumentExtractionError,
    extract_pages,
    index_document,
    split_document,
)
from app.services.vectorstore.chroma_client import faqs, knowledge_base

# Fixed namespace so the same source path always hashes to the same
# document_id across runs — that's what lets `index_document` delete a file's
# previous chunks before re-adding them, so re-running this script without
# `--reset` no longer accumulates duplicate vectors for unchanged files.
_CLI_DOCUMENT_NAMESPACE = uuid.UUID("6f6a9f0d-6e94-4b8b-9b8a-2f6a4b1e9c11")


def _category_for(file_path: Path, root: Path) -> str:
    rel = file_path.relative_to(root)
    return rel.parts[0] if len(rel.parts) > 1 else "root"


def _document_id_for(source: str) -> str:
    return uuid.uuid5(_CLI_DOCUMENT_NAMESPACE, source).hex


def ingest_knowledge_base(root: Path) -> int:
    total_chunks = 0
    for file_path in sorted(root.rglob("*")):
        if not (file_path.is_file() and file_path.suffix.lower() in KB_SUFFIXES):
            continue

        source = str(file_path.relative_to(root))
        category = _category_for(file_path, root)

        try:
            pages = extract_pages(file_path)
            chunks = split_document(pages)
        except DocumentExtractionError as e:
            print(f"skip (extraction failed): {file_path} ({e})")
            continue

        if not chunks:
            print(f"skip (empty): {file_path}")
            continue

        document_id = _document_id_for(source)
        chunk_count = index_document(document_id, file_path.name, category, source, chunks)
        print(f"ingested {chunk_count} chunk(s) from {source}")
        total_chunks += chunk_count
    return total_chunks


def ingest_faqs(root: Path) -> int:
    total_entries = 0
    for file_path in sorted(root.rglob("*.json")):
        print(f"Reading: {file_path}")
        entries = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            print(f"skip (not a JSON array): {file_path}")
            continue

        source = str(file_path.relative_to(root))

        documents, metadatas, ids, questions = [], [], [], []
        for entry in entries:
            question = entry["question"].strip()
            answer = entry["answer"].strip()
            keywords = entry.get("keywords") or []
            documents.append(f"Q: {question}\nA: {answer}")
            questions.append(question)
            metadatas.append(
                {
                    "source": source,
                    "category":  _category_for(file_path, root),
                    "question": question,
                    "id": entry["id"],
                    "keywords": ", ".join(keywords),
                }
            )
            ids.append(entry["id"])

        if not documents:
            print(f"skip (empty): {file_path}")
            continue

        # Embed the question only (not the stored Q+A document) so a short
        # user query is compared against a same-length question vector
        # instead of being diluted by answer text; the full Q+A is still
        # stored and returned as the retrieved document.
        embeddings = faqs._embedding_function(questions)
        faqs.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
        print(f"ingested {len(documents)} FAQ(s) from {source}")
        total_entries += len(documents)
    return total_entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", required=True, choices=["knowledge_base", "faq"])
    parser.add_argument("--path", required=True, type=Path, help="Root folder to ingest from")
    parser.add_argument("--reset", action="store_true", help="Delete all existing entries in the target collection first")
    args = parser.parse_args()

    if not args.path.is_dir():
        sys.exit(f"not a directory: {args.path}")

    collection = knowledge_base if args.collection == "knowledge_base" else faqs

    if args.reset:
        existing = collection.get()["ids"]
        if existing:
            collection.delete(ids=existing)
        print(f"cleared {len(existing)} existing entr(ies) from '{args.collection}'")

    if args.collection == "knowledge_base":
        total = ingest_knowledge_base(args.path)
    else:
        total = ingest_faqs(args.path)

    print(f"done — {total} item(s) ingested into '{args.collection}'")


if __name__ == "__main__":
    main()
