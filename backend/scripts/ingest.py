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

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.vectorstore.chroma_client import faqs, knowledge_base

KB_SUFFIXES = {".txt", ".md", ".pdf", ".docx"}
_SPLITTER = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)


def _category_for(file_path: Path, root: Path) -> str:
    rel = file_path.relative_to(root)
    return rel.parts[0] if len(rel.parts) > 1 else "root"


def _load_text(file_path: Path) -> str:
    if file_path.suffix == ".pdf":
        return "\n\n".join(d.page_content for d in PyPDFLoader(str(file_path)).load())
    if file_path.suffix == ".docx":
        return "\n\n".join(d.page_content for d in Docx2txtLoader(str(file_path)).load())
    return TextLoader(str(file_path), encoding="utf-8").load()[0].page_content


def ingest_knowledge_base(root: Path) -> int:
    total_chunks = 0
    for file_path in sorted(root.rglob("*")):
        if not (file_path.is_file() and file_path.suffix.lower() in KB_SUFFIXES):
            continue

        text = _load_text(file_path)
        if not text.strip():
            print(f"skip (empty): {file_path}")
            continue

        chunks = _SPLITTER.split_text(text)
        source = str(file_path.relative_to(root))
        category = _category_for(file_path, root)

        knowledge_base.add(
            ids=[f"{source}::{i}::{uuid.uuid4().hex[:8]}" for i in range(len(chunks))],
            documents=chunks,
            metadatas=[{"source": source, "category": category, "chunk": i} for i in range(len(chunks))],
        )
        print(f"ingested {len(chunks)} chunk(s) from {source}")
        total_chunks += len(chunks)
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
