# TEF Chatbot — Backend

FastAPI service exposing `POST /chat`, backed by a LangGraph pipeline:

```
refine query → extract intent/entities → FAQ layer (≤2 attempts)
  ├─ hit  → synthesize final answer
  └─ miss → KB layer (≤2 attempts)
              ├─ miss            → escalate to support
              └─ hit → confidence gate (KB-only)
                          ├─ pass → synthesize final answer
                          └─ fail → escalate to support
```

See the root [`README.md`](../README.md) for the overall project and [`CLAUDE.md`](../CLAUDE.md) for the full architecture reference.

## Setup

```
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

| Key | Purpose |
|---|---|
| `GROQ_API_KEY` | Groq API key, used for every LLM call in the pipeline |
| `GROQ_MODEL` | Groq model id (default `openai/gpt-oss-120b`) — pick one your key actually has access to, e.g. via `client.models.list()` |
| `DATABASE_URL` | Postgres connection string, used for `support_tickets` and the `knowledge_documents` admin registry |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD_HASH` / `ADMIN_AUTH_SECRET` | Single admin login gating `/api/admin/*` — see "Admin auth" below |
| `CHROMA_PERSIST_DIR` | Local folder Chroma persists to (default `./chroma_data`) |
| `FAQ_DATA_DIR` / `KB_DATA_DIR` | Source folders for ingestion (default `./faq`, `./knowledgebase`) |
| `FAQ_COLLECTION_NAME` / `KB_COLLECTION_NAME` | Chroma collection names |
| `FAQ_TOP_K` / `KB_TOP_K` | How many chunks to retrieve per layer |
| `FAQ_DISTANCE_THRESHOLD` / `KB_DISTANCE_THRESHOLD` | Cosine-distance cutoff for a "match" (lower = stricter) |
| `RETRY_LOOSEN_FACTOR` | How much the threshold relaxes on a layer's 2nd attempt |
| `MAX_LAYER_ATTEMPTS` | Retries per layer before giving up (default 2) |
| `CONFIDENCE_THRESHOLD` | Minimum KB-layer confidence to answer instead of escalating |
| `CONFIDENCE_RETRIEVAL_WEIGHT` | Weight of retrieval-similarity vs. LLM score in the KB confidence hybrid |
| `SUPPORT_EMAIL` / `SUPPORT_PHONE` | Contact info surfaced to the user on escalation |
| `FRONTEND_ORIGIN` | Allowed CORS origin for the React app |
| `KB_MAX_UPLOAD_MB` | Max file size (MB) accepted by the admin knowledge-base upload endpoint (default 10) |

`GROQ_API_KEY` and `DATABASE_URL` are secrets — `.env` is gitignored, never commit it.

You also need a reachable Postgres database matching `DATABASE_URL` (only used for `support_tickets` — create the role/db yourself if they don't exist yet, e.g. `createuser <user> && createdb -O <user> tef_chatbot`). Tables are created automatically on app startup (`Base.metadata.create_all` in `app/main.py`), no migration step needed.

## Content layout

FAQs and knowledge-base documents live in parallel, per-category folder trees:

```
backend/
  faq/<Category>/*.json             # [{ "question": "...", "answer": "..." }, ...]
  knowledgebase/<Category>/*.docx|.pdf|.txt|.md
```

Categories are just folder names — nothing in the code hardcodes a fixed category list (`app/services/query_understanding.py`'s `list_categories()` derives valid intents from whatever folders exist under `faq/` at request time, and the knowledge-base ingestion path — CLI or admin API — accepts any category name). Both `faq/` and `knowledgebase/` currently start empty (portfolio content is added per-deployment, not checked in) — create category folders as needed, or let the admin dashboard's upload form create one for you. Add a `.json` file to `faq/<Category>/` (any filename, `*.json`) in this shape:

```json
[
  { "question": "How do I pair a mentor with an entrepreneur?", "answer": "..." },
  { "question": "...", "answer": "..." }
]
```

## Ingestion

Run after adding/changing content in either folder:

```
python -m scripts.ingest --collection knowledge_base --path ./knowledgebase
python -m scripts.ingest --collection faq             --path ./faq
```

Add `--reset` to clear a collection entirely before re-ingesting.

For the knowledge-base collection specifically, `--reset` is no longer required just to pick up edits to an existing file: each file is indexed under a `document_id` derived from its path, and re-ingesting a file first deletes that file's previous chunks before adding the new ones (see `app/services/knowledge_base/ingestion.py`), so running the command again after editing a file won't leave stale chunks behind. `--reset` is still the right tool for removing chunks belonging to files you deleted from disk, or for clearing a collection outright. FAQ ingestion (`--collection faq`) is unchanged and still needs `--reset` after edits.

This same ingestion/indexing code is shared with the **admin knowledge-base API** below — uploading a file through the dashboard and running this CLI script both go through `app/services/knowledge_base/ingestion.py`, so there's one place that knows how to turn a file into indexed Chroma chunks.

## Admin auth

A single hardcoded admin account (`app/services/auth.py`, `app/api/routes/admin_auth.py`) gates every `/api/admin/*` route:

- `POST /api/admin/auth/login` — body `{"email": "...", "password": "..."}`, returns `{"token": "...", "email": "..."}` on success, `401` otherwise.
- Every route in the admin knowledge-base API below requires `Authorization: Bearer <token>` (enforced by the `require_admin` dependency attached to that whole router) — a missing/invalid/expired token gets `401`.
- The token is an HMAC-signed `{email, exp}` payload (12h TTL by default, `ADMIN_SESSION_TTL_SECONDS`), not a database session — nothing to revoke server-side short of rotating `ADMIN_AUTH_SECRET`, which invalidates every outstanding token.
- The password itself is never stored: `ADMIN_PASSWORD_HASH` is `HMAC-SHA256(ADMIN_AUTH_SECRET, password)`. Generate both for a new password:
  ```
  python -c "import secrets; print(secrets.token_hex(32))"                                            # -> ADMIN_AUTH_SECRET
  python -c "import hmac,hashlib; print(hmac.new(b'<ADMIN_AUTH_SECRET>', b'<password>', hashlib.sha256).hexdigest())"  # -> ADMIN_PASSWORD_HASH
  ```
- This is a one-account, no-signup, no-password-reset design — appropriate for a solo-admin portfolio deployment, not a multi-user production system.

## Admin Knowledge Base API

`app/api/routes/admin_knowledge_base.py`, mounted at `/api/admin/knowledge-base`, lets an admin manage knowledge-base documents over HTTP instead of the CLI — see the root [`README.md`](../README.md#knowledge-base-management) for the user-facing walkthrough and the frontend's `/admin` dashboard. Every endpoint below requires the admin session described above. Endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/documents` | Upload (`multipart/form-data`: `file`, `category`), extract, chunk, and index a document |
| `GET` | `/documents` | List all registered documents (status, category, chunk count, etc.) |
| `DELETE` | `/documents/{document_id}` | Delete a document's file, Chroma vectors, and registry row |
| `POST` | `/documents/{document_id}/reindex` | Re-extract/re-chunk/re-index a document from the file already on disk, replacing its previous vectors |
| `GET` | `/stats` | Total indexed documents / chunks / categories (+ per-category counts) |

Document metadata (filename, category, status, chunk count, timestamps, error message) lives in the `knowledge_documents` table (`KnowledgeDocument` in `app/db/models.py`) — this is the source of truth for the dashboard, not in-memory state, so it survives a backend restart. Each Chroma chunk is tagged with the owning document's stable `document_id`, plus `filename`/`category`/`chunk` index and, for PDFs, a `page` number (never invented for formats without one) — this is what makes "delete/re-index this document's vectors only" possible without touching any other document's chunks.

**Auth**: every route above requires an admin session — see `app/services/auth.py` and `app/api/routes/admin_auth.py` (`POST /api/admin/auth/login`). This is a single hardcoded email/password account (no user table, no signup, no password reset), configured via `ADMIN_EMAIL`/`ADMIN_PASSWORD_HASH`/`ADMIN_AUTH_SECRET` (see below) — appropriate for a solo-admin portfolio project, not a multi-admin production deployment.

Run the test suite (isolated from the real `chroma_data/`/`knowledgebase/`/database via `tests/conftest.py`, which points every dependency at a temp directory before `app` is ever imported):

```
pytest
```

## Running

```
uvicorn app.main:app --reload
```

- `GET /health` — liveness check
- `POST /chat` — body `{"user_id": "...", "message": "..."}`, returns:
  ```json
  {
    "answer": "...",
    "confidence": 0.82,
    "escalated": false,
    "answered_by": "faq",
    "support_email": null,
    "support_phone": null,
    "sources": ["common/general.json"]
  }
  ```
  `confidence` is `null` for FAQ answers (not confidence-gated). `answered_by` is `null` and `support_email`/`support_phone` are populated when `escalated` is `true`.

Quick manual check once the server is up:

```
curl -s localhost:8000/chat -H 'content-type: application/json' \
  -d '{"user_id": "dev", "message": "How do I reset my password?"}' | python -m json.tool
```

## Pipeline internals

- `app/services/graph/state.py` — the shared `ChatState` schema threaded through every node
- `app/services/graph/pipeline_graph.py` — the LangGraph `StateGraph` wiring (nodes + conditional edges)
- `app/services/query_refiner.py`, `intent_extractor.py` — pre-processing nodes (intent is classified against the live category folders under `faq/`)
- `app/services/retrieval/faq_layer.py`, `kb_layer.py` — the two retrieval layers (each retries up to `MAX_LAYER_ATTEMPTS` times via `app/services/retrieval/shared.py`, scoped to the classified intent's category on the first attempt)
- `app/services/retrieval/confidence.py` — KB-only confidence gate (retrieval similarity + LLM context-sufficiency hybrid)
- `app/services/synthesis.py` — shared final-answer generation, used by both the FAQ-hit and KB-pass paths
- `app/services/support.py` — support ticket creation + escalation message
- `app/services/pipeline.py` — builds/invokes the graph per request, maps the result to a `ChatResult`
- `app/services/knowledge_base/ingestion.py`, `documents.py` — shared document extraction/chunking/Chroma-indexing (`ingestion.py`) and filename/category sanitization + the `KnowledgeDocument` registry CRUD (`documents.py`), used by both `scripts/ingest.py` and the admin API above
