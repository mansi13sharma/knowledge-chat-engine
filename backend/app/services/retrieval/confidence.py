import logging
import re

from app.core.config import settings
from app.services.graph.state import ChatState
from app.services.llm import chat_completion

logger = logging.getLogger("app.services.confidence")

_SYSTEM_PROMPT = (
    "You are grading whether retrieved context excerpts are enough to answer a user's "
    "question, for a support chatbot deciding whether to answer or escalate to a human.\n\n"
    "Score from 0.0 to 1.0 using this rubric:\n"
    "1.0 - the excerpts directly and completely answer the question.\n"
    "0.7-0.9 - the excerpts answer the core of the question, even if minor details "
    "or edge cases aren't covered.\n"
    "0.4-0.6 - the excerpts are on-topic and partially useful but leave out "
    "significant parts of the answer.\n"
    "0.1-0.3 - the excerpts are only tangentially related.\n"
    "0.0 - the excerpts are unrelated to the question.\n\n"
    "Give partial credit generously: a partially useful excerpt is still useful. "
    "Respond with ONLY the number (e.g. \"0.8\"), no words, no explanation."
)

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _retrieval_score(hits: list[dict]) -> float:
    # Cosine distance is bounded [0, 2]; convert to a [0, 1] similarity score.
    similarities = [max(0.0, min(1.0, 1 - (h["distance"] / 2))) for h in hits]
    return sum(similarities) / len(similarities) if similarities else 0.0


def _llm_context_score(query: str, hits: list[dict], fallback: float) -> float:
    context = "\n\n".join(h["document"] for h in hits)
    user_prompt = f"Question: {query}\n\nContext:\n{context}"
    raw = chat_completion(_SYSTEM_PROMPT, user_prompt, temperature=0).strip()
    # Models sometimes ignore the "number only" instruction and add a stray
    # word or explanation despite it; pull the first number out rather than
    # requiring an exact match so that doesn't zero out an otherwise-good score.
    match = _NUMBER_RE.search(raw)
    if not match:
        logger.warning("Confidence: No number found in LLM response '%s'. Falling back to retrieval score.", raw)
        return fallback
    return max(0.0, min(1.0, float(match.group())))


def score_confidence(state: ChatState) -> dict:
    hits = state.get("kb_hits", [])
    retrieval_score = _retrieval_score(hits)
    llm_score = _llm_context_score(state["refined_query"], hits, fallback=retrieval_score)

    weight = settings.confidence_retrieval_weight
    confidence = weight * retrieval_score + (1 - weight) * llm_score
    logger.info(
        "Confidence: retrieval=%.2f llm=%.2f combined=%.2f (threshold=%.2f)",
        retrieval_score, llm_score, confidence, settings.confidence_threshold,
    )
    return {"confidence": confidence}


def confidence_router(state: ChatState) -> str:
    if (state.get("confidence") or 0.0) >= settings.confidence_threshold:
        return "pass"
    return "fail"
