# TEF Chatbot

A chatbot that answers user queries using FAQs and a knowledge base (RAG), orchestrated as a LangGraph pipeline. Low-confidence answers are escalated to a human support agent instead of being sent to the user.

## How it works

```
User → React chat UI → POST /chat → LangGraph pipeline → answer / escalation
```

1. **Refine** — the raw message is rewritten into a clear, self-contained query (spelling/typo correction).
2. **Intent + entity extraction** — an LLM call tags the query with an intent and any entities.
3. **FAQ layer** — semantic search against a Chroma collection built from `backend/faq/`. Up to 2 attempts (the 2nd reformulates the query and loosens the match threshold). On a hit, goes straight to answer synthesis — FAQ answers are **not** confidence-gated.
4. **Knowledge base layer** — reached only if the FAQ layer misses both attempts. Semantic search against a Chroma collection built from `backend/knowledgebase/`, also up to 2 attempts.
5. **Confidence gate** — the *only* point confidence is scored, and only for the KB layer: a hybrid of retrieval similarity + an LLM context-sufficiency score.
6. **Synthesis or escalation** — a passing FAQ/KB match is sent (top-k chunks + refined query) to the LLM for a final answer. A miss on both layers, or a low KB confidence score, creates a support ticket and returns a message with a support email/phone instead.

## Tech stack

- **Frontend**: React (Vite) — [`frontend/`](frontend/)
- **Backend**: Python (FastAPI) — [`backend/`](backend/)
- **Orchestration**: [LangGraph](https://langchain-ai.github.io/langgraph/) — the pipeline above is a `StateGraph` with retry loops and conditional edges. LangChain is used only for document loading/chunking in the ingestion script.
- **LLM**: [Groq](https://groq.com/)
- **Vector DB**: [Chroma](https://www.trychroma.com/), persisted locally, two collections (FAQ, knowledge base), local embeddings (no external embeddings API/key needed)
- **Database**: PostgreSQL via SQLAlchemy (support tickets only)

See [`backend/README.md`](backend/README.md) and [`frontend/README.md`](frontend/README.md) for setup details of each half, [`CLAUDE.md`](CLAUDE.md) for the full architecture reference, and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for diagrams of the system, the LangGraph chat flow, and the admin knowledge-base flow.

## Knowledge Base Management

An admin dashboard at the frontend's `/admin` route lets you manage the chatbot's knowledge-base documents through the UI instead of manually copying files into `backend/knowledgebase/` and running the ingestion script.

- **Supported formats**: PDF, DOCX, TXT, MD (rejected otherwise), up to `KB_MAX_UPLOAD_MB` (default 10 MB).
- **How upload works**: pick a category (freeform — no longer tied to any fixed list) and a file. The backend validates it, saves it under `backend/knowledgebase/<category>/`, extracts its text, splits it into chunks, and indexes those chunks into the existing Chroma `knowledge_base` collection — the same collection the chat pipeline's KB layer already queries, so a newly uploaded document is immediately answerable by the normal chatbot.
- **Where documents are stored**: `backend/knowledgebase/<category>/<filename>` — category and filename are sanitized (no `../`, no path separators) before ever touching the filesystem.
- **Registry**: each document's status (`processing` / `indexed` / `failed`), chunk count, and metadata live in a `knowledge_documents` Postgres table (`KnowledgeDocument` model) — this is the source of truth for the dashboard, not in-memory state, so it survives a backend restart.
- **Re-index**: re-extracts and re-chunks the document from the file already on disk, deleting its previous Chroma vectors first — repeated re-indexing never accumulates duplicate vectors for the same document.
- **Delete**: removes the file, its `knowledge_documents` row, and all of its Chroma vectors.
- **Required env vars**: `KB_MAX_UPLOAD_MB` (backend, see `backend/.env.example`) and `VITE_API_BASE_URL` (frontend, see `frontend/.env.example`).
- **Access**: run both apps as below, then open `http://localhost:5173/admin`.

The manual CLI ingestion path (`python -m scripts.ingest ...`) still works and now shares the same underlying ingestion/indexing code as the admin API — see [`backend/README.md`](backend/README.md#ingestion).

- **Access**: the admin API and dashboard are gated by a single hardcoded email/password admin account — log in at `/admin` with the credentials configured via `ADMIN_EMAIL`/`ADMIN_PASSWORD_HASH`/`ADMIN_AUTH_SECRET` in `backend/.env` (see `backend/README.md#admin-auth`). This is a one-account design (no signup, no password reset) suited to a solo-admin portfolio deployment, not a multi-user production system.

## Getting started

### Backend

```
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in GROQ_API_KEY, DATABASE_URL, support contact info
python -m scripts.ingest --collection knowledge_base --path ./knowledgebase
python -m scripts.ingest --collection faq --path ./faq
uvicorn app.main:app --reload
```

### Frontend

```
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL, defaults to http://127.0.0.1:8000
npm run dev
```

- `/` — the chat widget
- `/admin` — the knowledge-base admin dashboard (see above)

Requires a running PostgreSQL instance matching `DATABASE_URL` (used for support tickets and the knowledge-base document registry) and a `GROQ_API_KEY` for LLM calls. Chroma persists locally to `backend/chroma_data/` — no separate vector DB service needed.
