# Architecture

## 1. System overview

```mermaid
flowchart LR
    subgraph Frontend["Frontend — React (Vite)"]
        Chat["ChatPage (/)"]
        Admin["AdminPage (/admin)\nAdminLogin gate"]
    end

    subgraph Backend["Backend — FastAPI"]
        ChatAPI["POST /chat\nPOST /chat/feedback/ticket"]
        AuthAPI["POST /api/admin/auth/login"]
        KBAPI["/api/admin/knowledge-base/*\n(guarded by require_admin)"]
        Graph["LangGraph pipeline\n(pipeline.py)"]
        KBService["knowledge_base service\n(ingestion.py, documents.py)"]
    end

    CLI["scripts/ingest.py (CLI)"]

    Chroma[("ChromaDB\nfaqs / knowledge_base\ncollections")]
    Postgres[("PostgreSQL\nsupport_tickets\nknowledge_documents")]
    Groq(["Groq LLM API"])

    Chat -- "fetch" --> ChatAPI
    Admin -- "email + password" --> AuthAPI
    Admin -- "Bearer token" --> KBAPI

    ChatAPI --> Graph
    Graph -- "query" --> Chroma
    Graph -- "chat completion" --> Groq
    Graph -- "escalation ticket" --> Postgres

    KBAPI --> KBService
    KBAPI --> Postgres
    KBService -- "extract / chunk / index" --> Chroma
    CLI --> KBService
```

- **Two frontend routes**, one custom history-API router (no routing library): the chat widget and the admin dashboard, which sits behind a login screen.
- **Two ways into the knowledge base**: the admin dashboard (`/api/admin/knowledge-base`) and the CLI script — both call the *same* `app/services/knowledge_base/` code, so there is one place that turns a file into indexed Chroma chunks.
- **Groq** is the only LLM provider, called from `app/services/llm.py` at several pipeline steps (refine/classify, FAQ relevance, KB confidence, synthesis, follow-up suggestions).
- **Postgres** stores only metadata/state — `support_tickets` (escalations) and `knowledge_documents` (the admin KB registry) — never file binaries or vectors.

## 2. Chat request flow (LangGraph pipeline)

```mermaid
flowchart TD
    Start(["User message"]) --> Refine["refine_and_classify\n(refine + intent/entities + chitchat flag)"]

    Refine -- "chitchat" --> Chitchat["chitchat_reply"] --> End(["Response"])

    Refine -- "question" --> FAQSearch["faq_search\n(attempt 1: category-scoped)"]
    FAQSearch -- "retry (attempt < max)" --> FAQSearch
    FAQSearch -- "found" --> FAQRelevance["check_faq_relevance\n(LLM judges best candidate)"]
    FAQSearch -- "give up" --> KBSearch

    FAQRelevance -- "relevant" --> Synthesize
    FAQRelevance -- "not relevant" --> KBSearch["kb_search\n(attempt 1: category-scoped)"]

    KBSearch -- "retry (attempt < max)" --> KBSearch
    KBSearch -- "found" --> Confidence["score_confidence\n(retrieval similarity + LLM sufficiency)"]
    KBSearch -- "give up" --> CheckEsc

    Confidence -- "pass" --> Synthesize["synthesize\n(top-k chunks + query -> LLM answer)"]
    Confidence -- "fail" --> CheckEsc["check_escalation"]

    CheckEsc -- "under max_followup_attempts" --> Followup["suggest_followups\n(3-5 clarifying questions)"]
    CheckEsc -- "over max_followup_attempts" --> Escalate["escalate\n(create SupportTicket)"]

    Followup -- "done" --> End
    Followup -- "still unresolved" --> Escalate

    Synthesize --> End
    Escalate --> End
```

- **FAQ answers are never confidence-gated** — a relevant FAQ hit goes straight to synthesis.
- **Confidence scoring only happens for the KB layer**, and only gates KB answers, never FAQ ones.
- Each retrieval layer retries up to `MAX_LAYER_ATTEMPTS` (default 2): attempt 1 is scoped to the classified intent's category, attempt 2 reformulates the query and loosens the match threshold across all categories.
- Escalation isn't immediate — `check_escalation` counts consecutive unsuccessful turns in `chat_history` and only escalates once `max_followup_attempts` is exceeded; until then it offers follow-up questions instead.

## 3. Admin Knowledge Base management flow

```mermaid
sequenceDiagram
    actor Admin
    participant UI as AdminPage (React)
    participant Auth as /api/admin/auth
    participant KB as /api/admin/knowledge-base
    participant Svc as knowledge_base service
    participant DB as Postgres (knowledge_documents)
    participant Vec as Chroma (knowledge_base)

    Admin->>UI: email + password
    UI->>Auth: POST /login
    Auth-->>UI: session token (HMAC-signed, 12h TTL)

    Admin->>UI: choose category + file, Upload
    UI->>KB: POST /documents (Bearer token)
    KB->>Svc: sanitize category/filename, validate type + size
    Svc-->>KB: safe path under backend/knowledgebase/<category>/
    KB->>DB: create KnowledgeDocument (status=processing)
    KB->>Svc: extract_pages -> split_document -> index_document
    Svc->>Vec: delete_document_vectors(doc_id) [no-op if new]
    Svc->>Vec: add chunks tagged with document_id/category/filename/page
    KB->>DB: mark_indexed(chunk_count)
    KB-->>UI: {document: {...status: indexed, chunks: N}}

    Admin->>UI: Re-index
    UI->>KB: POST /documents/{id}/reindex
    KB->>Svc: re-extract from file already on disk
    Svc->>Vec: delete old vectors -> insert fresh vectors
    KB-->>UI: updated chunk count (no duplicate vectors)

    Admin->>UI: Delete
    UI->>KB: DELETE /documents/{id}
    KB->>Vec: delete_document_vectors(doc_id)
    KB->>KB: unlink file from disk
    KB->>DB: delete KnowledgeDocument row
    KB-->>UI: {deleted: true}

    Note over Vec: A newly uploaded document is immediately<br/>retrievable by the normal chat pipeline —<br/>same Chroma "knowledge_base" collection.
```

- A document's `document_id` is stable across re-indexing, so `index_document` always deletes that document's previous vectors before adding new ones — repeated re-indexing never accumulates duplicates.
- All three mutating routes (upload/reindex/delete) sit behind the router-level `require_admin` dependency — a missing/invalid/expired Bearer token gets a `401` before any of this runs.

## Key files

| Concern | File |
|---|---|
| Graph wiring | `backend/app/services/graph/pipeline_graph.py` |
| Shared chat state | `backend/app/services/graph/state.py` |
| FAQ / KB retrieval | `backend/app/services/retrieval/{faq_layer,kb_layer,shared,confidence,faq_relevance}.py` |
| Escalation & follow-up | `backend/app/services/followup.py`, `backend/app/services/support.py` |
| LLM client | `backend/app/services/llm.py` (Groq) |
| Chroma client | `backend/app/services/vectorstore/chroma_client.py` |
| Ingestion (shared) | `backend/app/services/knowledge_base/{ingestion,documents}.py` |
| Admin auth | `backend/app/services/auth.py`, `backend/app/api/routes/admin_auth.py` |
| Admin KB API | `backend/app/api/routes/admin_knowledge_base.py` |
| DB models | `backend/app/db/models.py` (`SupportTicket`, `KnowledgeDocument`) |
| Chat UI | `frontend/src/pages/ChatPage.jsx` |
| Admin UI | `frontend/src/pages/AdminPage.jsx`, `frontend/src/components/admin/*` |
| Router | `frontend/src/App.jsx`, `frontend/src/router.js` |
