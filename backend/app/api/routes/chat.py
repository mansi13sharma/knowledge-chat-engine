import logging
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.pipeline import handle_message
from app.services.support import create_support_ticket

logger = logging.getLogger("app.api.routes.chat")
router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    user_id: str
    message: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    answer: str
    confidence: float | None = None
    escalated: bool
    answered_by: Literal["faq", "kb"] | None = None
    support_email: str | None = None
    support_phone: str | None = None
    sources: list[str] = []
    followup_suggestions: list[str] = []


@router.post("", response_model=ChatResponse)
def post_chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    logger.info("Received POST /chat request. User ID: %s, Message length: %d characters", request.user_id, len(request.message))
    try:
        history = [{"role": m.role, "content": m.content} for m in request.history]
        result = handle_message(db, request.user_id, request.message, history)
        logger.info(
            "Successfully processed message for User ID: %s. answered_by=%s confidence=%s escalated=%s",
            request.user_id, result.answered_by, result.confidence, result.escalated,
        )
        return ChatResponse(
            answer=result.answer,
            confidence=result.confidence,
            escalated=result.escalated,
            answered_by=result.answered_by,
            support_email=settings.support_email if result.escalated else None,
            support_phone=settings.support_phone if result.escalated else None,
            sources=result.sources,
            followup_suggestions=result.followup_suggestions,
        )
    except Exception as e:
        logger.error("Exception occurred while handling chat message for User ID: %s: %s", request.user_id, str(e), exc_info=True)
        raise e


class FeedbackTicketRequest(BaseModel):
    user_id: str
    query: str
    draft_answer: str | None = None


class FeedbackTicketResponse(BaseModel):
    ticket_id: str
    support_email: str
    support_phone: str


@router.post("/feedback/ticket", response_model=FeedbackTicketResponse)
def post_feedback_ticket(request: FeedbackTicketRequest, db: Session = Depends(get_db)) -> FeedbackTicketResponse:
    """Creates a support ticket from a user's negative end-of-chat feedback.

    Independent of the LangGraph escalation path (Layer 3) — this fires from
    the frontend's post-conversation feedback prompt, not from a low-confidence
    KB answer, so it always carries confidence=0.0 and its own reason tag.
    """
    logger.info("Received POST /chat/feedback/ticket request. User ID: %s", request.user_id)
    ticket = create_support_ticket(
        db,
        request.user_id,
        request.query,
        draft_answer=request.draft_answer,
        confidence=0.0,
        intent=None,
        entities=None,
        escalation_reason="user_feedback_negative",
    )
    return FeedbackTicketResponse(
        ticket_id=str(ticket.id),
        support_email=settings.support_email,
        support_phone=settings.support_phone,
    )
