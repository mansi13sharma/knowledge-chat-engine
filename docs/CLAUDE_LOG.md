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
