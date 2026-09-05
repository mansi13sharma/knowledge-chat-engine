from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.services.chitchat import chitchat_reply
from app.services.followup import (
    escalation_decision_router,
    followup_result_router,
    suggest_followups,
)
from app.services.graph.state import ChatState
from app.services.query_understanding import refine_and_classify
from app.services.retrieval.confidence import confidence_router, score_confidence
from app.services.retrieval.faq_layer import faq_router, faq_search
from app.services.retrieval.faq_relevance import check_faq_relevance, faq_relevance_router
from app.services.retrieval.kb_layer import kb_router, kb_search
from app.services.support import make_escalate_node
from app.services.synthesis import synthesize


def _check_escalation_node(state: ChatState) -> dict:
    """Pass-through node: exists only so escalation_decision_router can be
    attached as a conditional edge (routers dispatch from a node, not from
    another router)."""
    return {}


def _refine_and_classify_node(state: ChatState) -> dict:
    refined_query, intent, entities, is_chitchat = refine_and_classify(
        state["raw_message"], state.get("chat_history")
    )
    return {
        "refined_query": refined_query,
        "intent": intent,
        "entities": entities,
        "is_chitchat": is_chitchat,
    }


def _chitchat_router(state: ChatState) -> str:
    return "chitchat" if state.get("is_chitchat") else "question"


def build_graph(db: Session):
    """Compiled per-request so the escalate node can close over this request's
    DB session — the graph itself completes within a single request/response
    cycle, so there's no need for LangGraph checkpointing/persistence here."""
    graph = StateGraph(ChatState)

    graph.add_node("refine_and_classify", _refine_and_classify_node)
    graph.add_node("chitchat", chitchat_reply)
    graph.add_node("faq_search", faq_search)
    graph.add_node("check_faq_relevance", check_faq_relevance)
    graph.add_node("kb_search", kb_search)
    graph.add_node("score_confidence", score_confidence)
    graph.add_node("synthesize", synthesize)
    graph.add_node("check_escalation", _check_escalation_node)
    graph.add_node("suggest_followups", suggest_followups)
    graph.add_node("escalate", make_escalate_node(db))

    graph.set_entry_point("refine_and_classify")
    graph.add_conditional_edges(
        "refine_and_classify",
        _chitchat_router,
        {"chitchat": "chitchat", "question": "faq_search"},
    )

    graph.add_conditional_edges(
        "faq_search",
        faq_router,
        {"found": "check_faq_relevance", "retry": "faq_search", "give_up": "kb_search"},
    )
    graph.add_conditional_edges(
        "check_faq_relevance",
        faq_relevance_router,
        {"relevant": "synthesize", "not_relevant": "kb_search"},
    )
    graph.add_conditional_edges(
        "kb_search",
        kb_router,
        {"found": "score_confidence", "retry": "kb_search", "give_up": "check_escalation"},
    )
    graph.add_conditional_edges(
        "score_confidence",
        confidence_router,
        {"pass": "synthesize", "fail": "check_escalation"},
    )
    graph.add_conditional_edges(
        "check_escalation",
        escalation_decision_router,
        {"clarify": "suggest_followups", "escalate": "escalate"},
    )
    graph.add_conditional_edges(
        "suggest_followups",
        followup_result_router,
        {"done": END, "escalate": "escalate"},
    )

    graph.add_edge("chitchat", END)
    graph.add_edge("synthesize", END)
    graph.add_edge("escalate", END)

    return graph.compile()
