import logging

from app.core.config import settings
from app.services.graph.state import ChatState
from app.services.retrieval.shared import search_with_retry
from app.services.vectorstore.chroma_client import knowledge_base

logger = logging.getLogger("app.services.kb_layer")


def kb_search(state: ChatState) -> dict:
    attempt = state.get("kb_attempt", 0) + 1
    logger.info("KBLayer: Attempt %d/%d", attempt, settings.max_layer_attempts)

    query, hits = search_with_retry(
        knowledge_base,
        state,
        attempt,
        settings.kb_distance_threshold,
        settings.kb_top_k,
        settings.retry_loosen_factor,
    )

    update: dict = {"kb_attempt": attempt, "kb_query": query, "kb_hits": hits}
    if hits:
        logger.info("KBLayer: %d hit(s) found on attempt %d", len(hits), attempt)
        update["retrieved_chunks"] = hits
        update["answered_by"] = "kb"
    else:
        logger.info("KBLayer: No hits within threshold on attempt %d", attempt)
    return update


def kb_router(state: ChatState) -> str:
    if state.get("kb_hits"):
        return "found"
    if state.get("kb_attempt", 0) < settings.max_layer_attempts:
        return "retry"
    return "give_up"
