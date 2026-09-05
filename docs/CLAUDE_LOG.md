# Claude Change Log

## 2026-07-23 14:00
Files Modified: backend/app/services/followup.py
Comment: Removed line-parsing fallback in _parse_suggestions so any unparseable/malformed LLM response yields no suggestions, guaranteeing escalation (via existing followup_result_router) instead of a fabricated non-empty suggestion.

## 2026-07-23 15:30
Files Modified: frontend/src/App.jsx, frontend/src/App.css, backend/app/api/routes/chat.py
Comment: Added end-of-chat feedback flow — client-side detection of conversation-ending phrases or 1.5min inactivity prompts the user for satisfaction; "not satisfied" offers Continue Chat or Create Support Ticket (new POST /chat/feedback/ticket endpoint), independent of the existing LangGraph escalation path.

## 2026-07-23 16:45
Files Modified: frontend/src/App.jsx, frontend/src/App.css
Comment: Fixed the end-of-chat star rating (was calling an undefined handleRating, crashing on click), added an optional comment textarea alongside it, and cleaned up leftover dead code/inline styles in the message and suggestion-card markup.

## 2026-07-27 00:00
Files Modified: frontend/src/App.css
Comment: Darkened the feedback star rating buttons (grayscale+brightness filter instead of low opacity) and added a circular border so they're clearly visible against the white feedback card background.

## 2026-09-05 13:45
Files Modified: backend/app/core/config.py, backend/app/db/models.py, backend/app/services/knowledge_base/__init__.py, backend/app/services/knowledge_base/documents.py, backend/app/services/knowledge_base/ingestion.py, backend/app/api/routes/admin_knowledge_base.py, backend/app/main.py, backend/scripts/ingest.py, backend/requirements.txt, backend/.env.example, backend/pytest.ini, backend/tests/conftest.py, backend/tests/test_admin_knowledge_base.py, backend/README.md, frontend/src/App.jsx, frontend/src/router.js, frontend/src/index.css, frontend/src/App.css, frontend/src/pages/ChatPage.jsx, frontend/src/pages/AdminPage.jsx, frontend/src/pages/AdminPage.css, frontend/src/components/admin/*, frontend/src/services/api.js, frontend/src/services/knowledgeBaseApi.js, frontend/src/utils/format.js, frontend/.env.example, frontend/.gitignore, frontend/README.md, README.md, CLAUDE.md
Comment: Added an admin Knowledge Base Management Dashboard (upload/list/re-index/delete KB documents via a new /api/admin/knowledge-base API and a new /admin frontend route), backed by a persistent KnowledgeDocument Postgres registry and a shared ingestion service (app/services/knowledge_base/) reused by both the CLI script and the new API so re-indexing never duplicates Chroma vectors; split the chat UI out of App.jsx into pages/ChatPage.jsx behind a minimal custom router.

## 2026-09-05 20:15
Files Modified: backend/app/core/config.py, backend/app/services/llm.py, backend/scripts/ingest.py, backend/tests/conftest.py, backend/.env.example, backend/README.md, README.md, CLAUDE.md, frontend/src/pages/ChatPage.jsx
Comment: Switched app/services/llm.py from OpenAI back to Groq (llama-3.3-70b-versatile was inaccessible on the provided key; defaulted to openai/gpt-oss-120b instead, confirmed available via client.models.list()); fixed scripts/ingest.py's FAQ ingestion to fall back to a generated stable id when a FAQ JSON entry has no "id" field (the new fitness/nutrition/healthy-lifestyle FAQ content didn't have one, which was crashing ingestion — both Chroma collections were actually empty, which is why FAQ-answerable questions were escalating instead); rebranded the chat landing page copy from the old TEF/mentor content to the new fitness-assistant content.

## 2026-09-05 20:45
Files Modified: backend/app/core/config.py, backend/app/services/auth.py, backend/app/api/routes/admin_auth.py, backend/app/api/routes/admin_knowledge_base.py, backend/app/main.py, backend/.env.example, backend/tests/conftest.py, backend/tests/test_admin_auth.py, backend/README.md, README.md, CLAUDE.md, frontend/src/services/api.js, frontend/src/services/authApi.js, frontend/src/components/admin/AdminLogin.jsx, frontend/src/pages/AdminPage.jsx, frontend/src/pages/AdminPage.css, frontend/src/components/admin/DocumentUpload.jsx, frontend/README.md
Comment: Added single-account email/password authentication gating the admin dashboard and its API — a new POST /api/admin/auth/login issues an HMAC-signed session token (password stored only as an HMAC hash, never plaintext), and every /api/admin/knowledge-base/* route now requires it via a router-level require_admin dependency; added a frontend login screen (localStorage-persisted token, auto-drops to login on a 401, logout button).
