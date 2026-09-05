# TEF Chatbot

A chatbot that answers user queries using FAQs and a knowledge base (RAG), orchestrated as a LangGraph pipeline. Low-confidence answers are escalated to a human support agent instead of being sent to the user.

## Architecture / request flow

1. User sends a message from the frontend.
2. **Refine + intent/entity extraction**: a single LLM call rewrites the raw message into a clear, self-contained query (typo/spelling correction), tags it with an intent label and any entities, and flags whether it's chitchat (greeting/thanks/small talk) rather than a real question.
3. **Chitchat branch**: if flagged chitchat, a lightweight node replies warmly and invites a real question, bypassing FAQ/KB/escalation entirely — chitchat never reaches the retrieval layers or creates a support ticket.
4. **FAQ layer** (Layer 1): semantic search against a dedicated FAQ Chroma collection, files stored under `backend/faq/`. Retried up to 2 attempts (query reformulation + loosened threshold on the 2nd try). On a hit, skips straight to synthesis — **FAQ answers are not confidence-gated**.
5. **Knowledge base layer** (Layer 2, reached only if FAQ misses both attempts): semantic search against the KB Chroma collection, files under `backend/knowledgebase/`. Also retried up to 2 attempts.
6. **Confidence gate** (KB-only): a hybrid of retrieval similarity + an LLM context-sufficiency score. This is the *only* point in the pipeline where confidence is scored.
7. **Synthesis**: on an FAQ hit or a passing KB confidence score, the top-k retrieved chunks + refined query are sent to the LLM to produce the final answer (one shared node for both success paths).
8. **Escalation check** (reached if neither layer finds a match, or KB confidence is below threshold): rather than escalating immediately, counts consecutive unsuccessful turns from `chat_history` (`app/services/followup.py`). If under `max_followup_attempts`, routes to **follow-up suggestion** — a short message plus 3-5 LLM-generated, topic-grounded clarifying questions returned as a structured `followup_suggestions: list[str]` field (not embedded in the answer text), so the frontend renders them as clickable chips that submit the chosen question as the next user message. Returned like a normal (non-escalated) answer. Only once that many consecutive unsuccessful turns have occurred does it route to **escalation** (Layer 3), which creates a `SupportTicket` row and returns a message with the configured support email/phone.

When working on any stage of this pipeline, preserve this routing order (FAQ → knowledge base → follow-up suggestion → escalation), the 2-attempt retry on each of the FAQ/KB layers, and the fact that confidence scoring only gates the KB layer — never send a low-confidence KB answer directly to the user, and never gate FAQ answers on confidence.

## Tech stack

- Frontend: React (Vite) — `frontend/`
- Backend: Python (FastAPI) — `backend/`
- Orchestration: LangGraph (`backend/app/services/graph/`) — the pipeline is a `StateGraph` with retry loops (FAQ/KB) and conditional edges (confidence gate, escalation). LangChain is used only inside the ingestion script for document loaders/text splitting, not for the graph itself.
- LLM: OPENAI (`backend/app/services/llm.py`)
- Vector DB: Chroma, persisted to `backend/chroma_data/`, two collections (`faqs`, `knowledge_base`) via `backend/app/services/vectorstore/chroma_client.py`. Embeddings are Chroma's bundled local default (no external embeddings API).
- Database: PostgreSQL via SQLAlchemy (`backend/app/db/`) — used only for `SupportTicket` rows now (FAQs moved to files, see below).

## Code layout

- `backend/app/api/routes/chat.py` — the single `POST /chat` endpoint
- `backend/app/services/pipeline.py` — builds the LangGraph, invokes it, maps the result to a `ChatResult`
- `backend/app/services/graph/state.py` — the shared `ChatState` TypedDict schema
- `backend/app/services/graph/pipeline_graph.py` — graph wiring (nodes + conditional edges)
- `backend/app/services/query_understanding.py` — combined refine + intent/entity extraction + chitchat-detection node (single LLM call), constrained to the category folders under `backend/faq/`
- `backend/app/services/chitchat.py` — lightweight reply node for greetings/small talk, bypasses FAQ/KB/escalation entirely
- `backend/app/services/retrieval/faq_layer.py`, `kb_layer.py` — the two retrieval layers (search node + router fn each), scoped to the classified intent's category on the first attempt
- `backend/app/services/retrieval/shared.py` — shared query-with-retry / query-reformulation helpers used by both layers
- `backend/app/services/retrieval/confidence.py` — KB-only confidence gate (retrieval similarity + LLM context-sufficiency hybrid)
- `backend/app/services/synthesis.py` — shared answer-synthesis node (used by both FAQ and KB success paths)
- `backend/app/services/followup.py` — follow-up-question node + the escalation-decision router (counts consecutive unsuccessful turns from `chat_history`, gated by `settings.max_followup_attempts`)
- `backend/app/services/support.py` — support ticket creation + escalation node
- `backend/app/db/models.py` — `SupportTicket` table
- `backend/faq/<Category>/*.json` — FAQ content, one JSON array of `{question, answer}` per file, category folders mirror `backend/knowledgebase/`
- `backend/knowledgebase/<Category>/...` — knowledge-base source documents (.docx/.pdf/.txt/.md)
- `backend/scripts/ingest.py` — ingestion script for both collections: `python -m scripts.ingest --collection knowledge_base --path ./knowledgebase` / `--collection faq --path ./faq`

`backend/faq/` currently only has placeholder/general FAQ content (`Common/general.json`) plus empty per-category `readme.md` markers — real FAQ authoring per category is an ongoing content task, not a code task. After adding/editing a `.json` file there, re-run the `faq` ingestion command above (add `--reset` first if you edited existing entries rather than just adding new ones).

## Conventions

- Backend: run from `backend/` with a venv (`python3 -m venv .venv`), deps in `requirements.txt`, config via `.env` (see `.env.example`) loaded through `app/core/config.py` (pydantic-settings).
- Frontend: standard Vite React app in `frontend/`, run with `npm install && npm run dev`.
- Secrets (`OPENAI_API_KEY`, `DATABASE_URL`) live in `backend/.env`, which is gitignored — never commit it.

## Automatic Change Logging

After completing any task that modifies project files:

For every task that modifies one or more project files:

- Ensure `docs/CLAUDE_LOG.md` exists.
- If it does not exist, create it automatically.
- After completing the task, append a new entry to the log.
- Each entry must contain:
  - Date & Time
  - Files Modified (comma-separated)
  - One-line Comment
- Never overwrite or delete previous entries.
- If no project files were modified, do not update the log.
- Consider updating `docs/CLAUDE_LOG.md` a required part of every code change.