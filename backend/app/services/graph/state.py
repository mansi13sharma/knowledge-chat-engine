from typing import Literal, TypedDict

from app.services.vectorstore.chroma_client import RetrievedChunk


class ChatState(TypedDict, total=False):
    user_id: str
    raw_message: str
    chat_history: list[dict[str, str]]
    refined_query: str
    intent: str
    entities: dict[str, str]
    is_chitchat: bool

    faq_attempt: int
    faq_query: str
    faq_hits: list[RetrievedChunk]
    faq_relevant: bool | None

    kb_attempt: int
    kb_query: str
    kb_hits: list[RetrievedChunk]

    retrieved_chunks: list[RetrievedChunk]
    answered_by: Literal["faq", "kb"] | None
    confidence: float | None

    answer: str | None
    escalated: bool
    escalation_reason: Literal["not_found", "low_confidence"] | None
    sources: list[str]
    followup_suggestions: list[str]
