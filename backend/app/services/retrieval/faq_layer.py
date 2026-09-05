import logging

from app.core.config import settings
from app.services.graph.state import ChatState
from app.services.retrieval.shared import search_with_retry
from app.services.vectorstore.chroma_client import faqs

logger = logging.getLogger("app.services.faq_layer")


def faq_search(state: ChatState) -> dict:
    attempt = state.get("faq_attempt", 0) + 1
    logger.info("FAQLayer: Attempt %d/%d", attempt, settings.max_layer_attempts)

    query, hits = search_with_retry(
        faqs,
        state,
        attempt,
        settings.faq_distance_threshold,
        settings.faq_top_k,
        settings.retry_loosen_factor,
    )

    update: dict = {"faq_attempt": attempt, "faq_query": query, "faq_hits": hits}
    if hits:
        logger.info("FAQLayer: %d hit(s) found on attempt %d", len(hits), attempt)
        update["retrieved_chunks"] = hits
        update["answered_by"] = "faq"
    else:
        logger.info("FAQLayer: No hits within threshold on attempt %d", attempt)
    return update


def faq_router(state: ChatState) -> str:
    if state.get("faq_hits"):
        return "found"
    if state.get("faq_attempt", 0) < settings.max_layer_attempts:
        return "retry"
    return "give_up"
