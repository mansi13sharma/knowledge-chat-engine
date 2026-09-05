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
| `OPENAI_API_KEY` | OPENAI API key, used for every LLM call in the pipeline |
| `OPENAI_MODEL` | OPENAI model id (default `gpt-4o-mini`) |
| `DATABASE_URL` | Postgres connection string, used only for `support_tickets` |
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

`OPENAI_API_KEY` and `DATABASE_URL` are secrets — `.env` is gitignored, never commit it.

You also need a reachable Postgres database matching `DATABASE_URL` (only used for `support_tickets` — create the role/db yourself if they don't exist yet, e.g. `createuser <user> && createdb -O <user> tef_chatbot`). Tables are created automatically on app startup (`Base.metadata.create_all` in `app/main.py`), no migration step needed.

## Content layout

FAQs and knowledge-base documents live in parallel, per-category folder trees:

```
backend/
  faq/<Category>/*.json             # [{ "question": "...", "answer": "..." }, ...]
  knowledgebase/<Category>/*.docx|.pdf|.txt|.md
```

Category folders currently present in both trees: `audit/`, `common/`, `entrepreneur Onboarding/`, `lms/`, `m&e/`, `mentorship/`, `pitching/` — each `knowledgebase/<Category>` holds the real manuals, each `faq/<Category>` should hold that category's FAQ JSON file(s) (`common/` is for general, cross-category FAQs like "How do I reset my password?"). Only `faq/common/general.json` has real content today; the other category folders just have an empty `readme.md` placeholder — add a `.json` file there (any filename, `*.json`) in this shape:

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

Add `--reset` to clear a collection before re-ingesting (needed if you edited or removed existing entries, not just added new ones — otherwise stale chunks stay in Chroma alongside the new ones).

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
