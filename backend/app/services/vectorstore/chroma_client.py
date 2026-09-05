from typing import TypedDict

import chromadb

from app.core.config import settings

_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)

# hnsw:space=cosine keeps distances bounded to [0, 2] so the configured
# distance thresholds stay meaningful regardless of chromadb version defaults.
faqs = _client.get_or_create_collection(
    name=settings.faq_collection_name, metadata={"hnsw:space": "cosine"}
)
knowledge_base = _client.get_or_create_collection(
    name=settings.kb_collection_name, metadata={"hnsw:space": "cosine"}
)


class RetrievedChunk(TypedDict):
    document: str
    metadata: dict
    distance: float


def query_collection(
    collection, query_text: str, n_results: int, category: str | None = None
) -> list[RetrievedChunk]:
    count = collection.count()
    if count == 0:
        return []
    where = {"category": category} if category else None
    results = collection.query(
        query_texts=[query_text], n_results=min(n_results, count), where=where
    )
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    return [
        {"document": doc, "metadata": meta or {}, "distance": dist}
        for doc, meta, dist in zip(documents, metadatas, distances)
    ]
