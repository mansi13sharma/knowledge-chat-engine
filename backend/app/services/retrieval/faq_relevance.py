import logging
import re

from app.services.graph.state import ChatState
from app.services.llm import chat_completion
from app.services.vectorstore.chroma_client import RetrievedChunk

logger = logging.getLogger("app.services.faq_relevance")

# Deliberately not the KB confidence rubric: FAQ hits are independent Q&A
# candidates (see ingest.py, each embedded on its question alone), so this
# judges each one on its own merits rather than averaging/blending them into
# one context the way confidence.py does for KB chunks.
_SYSTEM_PROMPT = (
    "You are checking candidate FAQ question/answer pairs for a support chatbot "
    "that must decide whether to answer directly from an FAQ or fall back to a "
    "broader knowledge-base search.\n\n"
    "Each numbered candidate below is an independent Q&A pair retrieved by semantic "
    "search — judge each one on its own, do not combine information across "
    "candidates. A candidate counts as a match if its answer is clearly on the same "
    "topic as the user's question and would usefully inform them — even if the "
    "FAQ's own question is worded more narrowly than the user's (e.g. it names a "
    "specific module, agreement, or process that the user asked about only in "
    "general terms). Only reject a candidate if its answer is about a "
    "substantively different topic that would not help the user at all.\n\n"
    "Respond with ONLY the number of the best matching candidate (e.g. \"2\"). "
    "If none of the candidates' answers would satisfy the user, respond with ONLY \"0\"."
)

_NUMBER_RE = re.compile(r"\d+")


def _format_candidates(hits: list[RetrievedChunk]) -> str:
    lines = []
    for i, h in enumerate(hits, start=1):
        lines.append(f"[{i}] {h['document']}")
    return "\n\n".join(lines)


def check_faq_relevance(state: ChatState) -> dict:
    hits = state.get("faq_hits") or []
    if not hits:
        return {"faq_relevant": False}

    query = state["refined_query"]
    user_prompt = f"User's question: {query}\n\nCandidates:\n{_format_candidates(hits)}"
    raw = chat_completion(_SYSTEM_PROMPT, user_prompt, temperature=0).strip()

    match = _NUMBER_RE.search(raw)
    index = int(match.group()) if match else 0

    if 1 <= index <= len(hits):
        logger.info(
            "FAQRelevance: candidate %d/%d judged a direct match for '%s'",
            index, len(hits), query,
        )
        return {"faq_relevant": True}

    logger.info(
        "FAQRelevance: no candidate among %d judged a direct match for '%s'; falling back to KB",
        len(hits), query,
    )
    return {"faq_relevant": False, "retrieved_chunks": [], "answered_by": None}


def faq_relevance_router(state: ChatState) -> str:
    return "relevant" if state.get("faq_relevant") else "not_relevant"
