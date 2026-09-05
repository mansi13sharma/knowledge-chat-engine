import json
import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import SupportTicket
from app.services.graph.state import ChatState

logger = logging.getLogger("app.services.support")


def create_support_ticket(
    db: Session,
    user_id: str,
    query: str,
    draft_answer: str | None,
    confidence: float,
    intent: str | None,
    entities: dict[str, str] | None,
    escalation_reason: str | None,
) -> SupportTicket:
    ticket = SupportTicket(
        user_id=user_id,
        query=query,
        draft_answer=draft_answer,
        confidence=confidence,
        intent=intent,
        entities_json=json.dumps(entities or {}),
        escalation_reason=escalation_reason,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    logger.info("Support: Created ticket %s (reason=%s)", ticket.id, escalation_reason)
    return ticket


def make_escalate_node(db: Session):
    def escalate(state: ChatState) -> dict:
        # Reached either because neither layer found a match (kb_hits empty)
        # or because the KB layer found hits but confidence scored too low.
        reason = "low_confidence" if state.get("kb_hits") else "not_found"
        create_support_ticket(
            db,
            state["user_id"],
            state["refined_query"],
            draft_answer=None,
            confidence=state.get("confidence") or 0.0,
            intent=state.get("intent"),
            entities=state.get("entities"),
            escalation_reason=reason,
        )
        message = (
            "Thanks for reaching out — I've escalated this to our support team, "
            "who will follow up with you shortly. "
            f"You can also reach them directly at {settings.support_email} or {settings.support_phone}."
        )
        return {"answer": message, "escalated": True, "escalation_reason": reason}

    return escalate
