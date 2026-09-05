# TEF Chatbot — Frontend

React (Vite) chat UI for the TEF Chatbot. Talks to the FastAPI backend's `POST /chat` endpoint (see [`../backend/README.md`](../backend/README.md)).

## Setup

```
cd frontend
npm install
npm run dev
```

Backend must be running at `http://127.0.0.1:8000` (hardcoded in `src/App.jsx` — there's no build-time env var for this yet).

## What it does

- Single-page chat window (`src/App.jsx`): suggestion cards on the empty state, a message list, and an input box.
- Shows a connection badge based on `GET /health`.
- Each bot reply displays:
  - a **layer badge** — "Answered from FAQ" for FAQ-layer answers (not confidence-scored), or a confidence pill for knowledge-base-layer answers
  - an **escalation banner** with the support email/phone (from the backend response) when the query was escalated to a human agent instead of answered

## Scripts

- `npm run dev` — dev server with HMR
- `npm run build` — production build to `dist/`
- `npm run lint` — oxlint
- `npm run preview` — preview the production build locally
