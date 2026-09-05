import json
import logging
from pathlib import Path

from app.core.config import settings
from app.services.llm import chat_completion

logger = logging.getLogger("app.services.query_understanding")

# "common" is the catch-all bucket (general/account-support FAQs live there),
# so it's always a valid fallback even if the folder listing below is empty.
_FALLBACK_CATEGORY = "common"


def list_categories() -> list[str]:
    """Category labels the FAQ/KB layers can filter on, derived from the
    folder structure under faq_data_dir rather than hardcoded, so new
    categories added on disk are picked up without a code change."""
    root = Path(settings.faq_data_dir)
    if not root.is_dir():
        return [_FALLBACK_CATEGORY]
    categories = sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    return categories or [_FALLBACK_CATEGORY]


def _build_system_prompt(categories: list[str]) -> str:
    return (
        "You will be given the recent conversation history (if any) followed by "
        "a raw new user message, which may contain spelling mistakes, typos, or "
        "shorthand. Process the new message in this order:\n"
        "1. First, correct it: fix spelling and typos, expand abbreviations, and "
        "make any implicit intent explicit, producing a clear, unambiguous, "
        "self-contained query. If the new message is a follow-up that relies on "
        "the conversation history (e.g. it uses pronouns like 'it'/'that', or "
        "omits a subject already established earlier, such as 'what about the "
        "deadline?'), rewrite it using the history so it stands alone without "
        "needing the history to be understood. Do not add information the user "
        "didn't imply, and do not pull in unrelated topics from earlier turns.\n"
        "2. Decide whether it is chitchat (greetings, thanks, farewells, small "
        "talk, or anything else that isn't actually asking for information) as "
        "opposed to a real question that needs an answer.\n"
        "3. Then, using that corrected query (not the raw original), classify it "
        f"into exactly one of these categories: {', '.join(categories)}. If "
        f"nothing else fits, or if it's chitchat, use '{_FALLBACK_CATEGORY}'. "
        "Also extract any clear entities from the corrected query, spelled "
        "correctly (chitchat messages have no entities).\n"
        "Respond with ONLY a JSON object of the exact shape "
        '{"refined_query": "<corrected query>", "intent": "<one_of_the_categories_above>", '
        '"entities": {"<name>": "<value>", ...}, "is_chitchat": <true or false>}. '
        "If there are no clear entities, use an empty object. Do not add commentary."
    )


def _format_history(history: list[dict[str, str]]) -> str:
    lines = []
    for turn in history:
        role = "User" if turn.get("role") == "user" else "Assistant"
        content = (turn.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def refine_and_classify(
    message: str, history: list[dict[str, str]] | None = None
) -> tuple[str, str, dict[str, str], bool]:
    """Single LLM call that rewrites the raw message into a refined query,
    classifies it into an intent category with entities, and flags whether
    it's chitchat rather than a real question — replacing what used to be
    two sequential LLM round-trips (refine, then extract). Recent chat
    history is included so follow-up messages (pronouns, omitted subjects)
    can be resolved into a self-contained query."""
    categories = list_categories()
    logger.info("QueryUnderstanding: Requesting refined query + intent/entities from LLM...")

    history_text = _format_history(history or [])
    user_prompt = (
        f"Conversation history:\n{history_text}\n\nNew message: {message}"
        if history_text
        else message
    )

    raw = chat_completion(_build_system_prompt(categories), user_prompt).strip()
    try:
        # Tolerate accidental markdown code fences around the JSON.
        cleaned = raw.strip("`").removeprefix("json").strip() if raw.startswith("```") else raw
        parsed = json.loads(cleaned)

        refined_query = str(parsed.get("refined_query") or "").strip() or message

        intent = str(parsed.get("intent") or "").strip()
        if intent not in categories:
            logger.warning("QueryUnderstanding: intent '%s' not in known categories %s. Falling back to '%s'.", intent, categories, _FALLBACK_CATEGORY)
            intent = _FALLBACK_CATEGORY

        entities = parsed.get("entities") or {}
        if not isinstance(entities, dict):
            entities = {}
        entities = {str(k): str(v) for k, v in entities.items()}

        is_chitchat = bool(parsed.get("is_chitchat", False))

        logger.info(
            "QueryUnderstanding: refined_query='%s' intent='%s' entities=%s is_chitchat=%s",
            refined_query, intent, entities, is_chitchat,
        )
        return refined_query, intent, entities, is_chitchat
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        logger.warning("QueryUnderstanding: Failed to parse LLM response '%s' (%s). Falling back to raw message / '%s'.", raw, e, _FALLBACK_CATEGORY)
        return message, _FALLBACK_CATEGORY, {}, False
