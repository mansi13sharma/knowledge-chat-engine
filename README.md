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

See [`backend/README.md`](backend/README.md) and [`frontend/README.md`](frontend/README.md) for setup details of each half, and [`CLAUDE.md`](CLAUDE.md) for the full architecture reference.

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
npm run dev
```

Requires a running PostgreSQL instance matching `DATABASE_URL` (used for support tickets) and a `GROQ_API_KEY` for LLM calls. Chroma persists locally to `backend/chroma_data/` — no separate vector DB service needed.
