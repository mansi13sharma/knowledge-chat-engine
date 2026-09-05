# TEF Chatbot — Frontend

React (Vite) UI for the TEF Chatbot: the chat widget and an admin knowledge-base dashboard. Talks to the FastAPI backend (see [`../backend/README.md`](../backend/README.md)).

## Setup

```
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL, defaults to http://127.0.0.1:8000
npm run dev
```

The backend origin is read from `VITE_API_BASE_URL` (see `src/services/api.js`) — no URL is hardcoded in components.

## Routes

- `/` — the chat widget (`src/pages/ChatPage.jsx`)
- `/admin` — the knowledge-base admin dashboard (`src/pages/AdminPage.jsx`)

Routing is a small custom history-API router (`src/App.jsx` + `src/router.js`) rather than a routing library, since there are only two routes.

## What it does

**Chat (`/`)**

- Single-page chat window: suggestion cards on the empty state, a message list, and an input box.
- Shows a connection badge based on `GET /health`.
- Each bot reply displays:
  - a **layer badge** — "Answered from FAQ" for FAQ-layer answers (not confidence-scored), or a confidence pill for knowledge-base-layer answers
  - an **escalation banner** with the support email/phone (from the backend response) when the query was escalated to a human agent instead of answered

**Admin (`/admin`)**

- Gated by a login screen (`src/components/admin/AdminLogin.jsx`) — email/password, checked against the backend's single hardcoded admin account (see `../backend/README.md#admin-auth`). The session token lives in `localStorage` and is attached as `Authorization: Bearer <token>` to every admin API call (`src/services/api.js`); a `401` response clears it and drops back to the login screen. A "Log out" button in the dashboard header clears it manually.
- Stat cards (total documents / chunks / categories), all backend-sourced (`GET /api/admin/knowledge-base/stats`).
- Upload form (category + file) with an inline success/error toast — no `alert()`.
- Document table with client-side search (filename) and category filter, re-index and delete actions (delete requires a confirmation modal), and a proper empty state when the knowledge base has no documents yet.
- API calls live in `src/services/knowledgeBaseApi.js` / `src/services/authApi.js` (built on the shared `src/services/api.js` fetch wrapper), not scattered across components.

## Scripts

- `npm run dev` — dev server with HMR
- `npm run build` — production build to `dist/`
- `npm run lint` — oxlint
- `npm run preview` — preview the production build locally
