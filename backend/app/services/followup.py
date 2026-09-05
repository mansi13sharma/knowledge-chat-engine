import json
import logging
import re

from app.core.config import settings
from app.services.graph.state import ChatState
from app.services.llm import chat_completion

logger = logging.getLogger("app.services.followup")

# Prefixed onto every follow-up message so later turns can recognize it in
# chat_history without any extra state — this is the only signal we have for
# "how many unsuccessful attempts in a row", since the graph is stateless
# across requests and history is round-tripped by the frontend.
_FOLLOWUP_PREFIX = (
    "I couldn't find a fully confident answer to that yet. Here are some "
    "related questions I can help with:"
)

_MIN_SUGGESTIONS = 2
_MAX_SUGGESTIONS = 3

_SYSTEM_PROMPT = (
    "A user asked a question on the TEF (Tony Elumelu Foundation) platform, but "
    "the retrieved knowledge base context wasn't confident/complete enough to "
    "answer directly. Do not answer the question and do not invent facts.\n\n"
    "First, judge whether the context excerpts below are actually relevant to "
    "the user's question and topic. If they are not relevant — e.g. they "
    "discuss a different feature, module, or workflow than what the user "
    "asked about — respond with an empty JSON array `[]` and nothing else. "
    "Do not suggest questions about the unrelated content just because it was "
    "retrieved.\n\n"
    f"Otherwise, suggest {_MIN_SUGGESTIONS}-{_MAX_SUGGESTIONS} follow-up "
    "questions that:\n"
    "- Are specific to the TEF platform's actual features and workflows (e.g. "
    "mentorship pairing, M&E enumerator/reviewer roles, audit processes, "
    "pitching, account/role management) — never generic chatbot filler like "
    "'can you clarify?' or 'what do you mean?'.\n"
    "- Are each directly related to the user's question and answerable from "
    "the context excerpts given below; do not invent a question about "
    "something not grounded in them, and never pull in an unrelated topic or "
    "module just because it appeared in the excerpts.\n"
    "- Stay closely related to the user's original topic, helping narrow down "
    "what they're looking for.\n"
    "- Are phrased as complete, standalone questions a user could click and "
    "send as-is — no 'or', no placeholders, no leading numbering/bullets.\n\n"
    "If you cannot come up with any question meeting all of the above, "
    "respond with an empty JSON array `[]` instead of forcing a weak or "
    "unrelated one.\n\n"
    "Respond with ONLY a JSON array of question strings (or `[]`), nothing "
    "else. Example JSON output: [\"How do I reset my password?\", \"How does "
    'a Mentor Admin pair an entrepreneur with a mentor?"]'
)


def _build_context(state: ChatState) -> str:
    hits = state.get("kb_hits") or state.get("faq_hits") or []
    return "\n\n".join(h["document"] for h in hits[:3])


_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _parse_suggestions(raw: str) -> list[str]:
    match = _JSON_ARRAY_RE.search(raw)
    if match:
        try:
            parsed = json.loads(match.group())
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(q).strip() for q in parsed if str(q).strip()][:_MAX_SUGGESTIONS]

    # No valid JSON array in the response — treat this the same as the model
    # deliberately returning `[]`. We never salvage a raw-text/line-based
    # guess here: any unparseable or malformed response must fall through to
    # escalation (see followup_result_router) rather than surface a
    # fabricated, possibly irrelevant "suggestion" to the user.
    logger.warning("Followup: No valid JSON array in LLM response '%s'. Treating as no suggestions.", raw)
    return []


def suggest_followups(state: ChatState) -> dict:
    context = _build_context(state)

    # No relevant context was retrieved at all, so there is nothing to ground
    # a directly-related follow-up in — skip the LLM call and let the
    # escalation router send this straight to the ticket flow instead of
    # returning empty/unrelated suggestions.
    if not context:
        logger.info(
            "Followup: No retrieved context for '%s' (intent=%s); skipping suggestions, routing to escalation.",
            state["refined_query"], state.get("intent"),
        )
        return {"escalated": False, "sources": [], "followup_suggestions": []}

    user_prompt = (
        f"User's question: {state['refined_query']}\nTopic: {state.get('intent') or 'general'}"
        f"\n\nRelated context excerpts (ground the suggested questions in these):\n{context}"
    )

    raw = chat_completion(_SYSTEM_PROMPT, user_prompt).strip()
    suggestions = _parse_suggestions(raw)

    logger.info(
        "Followup: Suggested %d clarifying question(s) for '%s' (intent=%s)",
        len(suggestions), state["refined_query"], state.get("intent"),
    )
    if not suggestions:
        return {"escalated": False, "sources": [], "followup_suggestions": []}

    return {
        "answer": _FOLLOWUP_PREFIX,
        "escalated": False,
        "sources": [],
        "followup_suggestions": suggestions,
    }


def followup_result_router(state: ChatState) -> str:
    """Routes to escalation when suggest_followups couldn't produce any
    suggestion directly related to the user's query (irrelevant/missing
    context, or the model returned `[]`), instead of surfacing empty chips."""
    return "done" if state.get("followup_suggestions") else "escalate"


def _consecutive_unsuccessful_attempts(chat_history: list[dict]) -> int:
    count = 0
    for msg in reversed(chat_history or []):
        if msg.get("role") != "assistant":
            continue
        if _FOLLOWUP_PREFIX in (msg.get("content") or ""):
            count += 1
        else:
            break
    return count


def escalation_decision_router(state: ChatState) -> str:
    attempts = _consecutive_unsuccessful_attempts(state.get("chat_history") or [])
    if attempts >= settings.max_followup_attempts:
        return "escalate"
    return "clarify"
