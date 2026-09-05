from app.services.vectorstore.chroma_client import knowledge_base

query = "If the entrepreneur fails to complete the LMS module within the timeline"

results = knowledge_base.query(
    query_texts=[query],
    n_results=10,
)

for i, (doc, distance, metadata) in enumerate(
    zip(
        results["documents"][0],
        results["distances"][0],
        results["metadatas"][0],
    ),
    start=1,
):
    print(f"\n--- Result {i} ---")
    print(f"Distance: {distance}")
    print(f"Metadata: {metadata}")
    print(f"Document:\n{doc}")