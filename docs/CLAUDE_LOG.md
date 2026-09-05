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
