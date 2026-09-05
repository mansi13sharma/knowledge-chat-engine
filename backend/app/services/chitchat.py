import logging

from app.services.graph.state import ChatState
from app.services.llm import chat_completion

logger = logging.getLogger("app.services.chitchat")

_SYSTEM_PROMPT = (
    "You are the TEF AI Assistant, responding to a casual message (a greeting, "
    "thanks, farewell, or small talk) rather than a real question. Reply warmly "
    "and briefly — one or two sentences — and invite the user to ask about TEF "
    "programmes, applications, mentorship, or related topics. Do not answer as "
    "if you were asked a real question, and do not invent any information."
)


def chitchat_reply(state: ChatState) -> dict:
    logger.info("Chitchat: Generating a short reply for '%s'", state["raw_message"])
    answer = chat_completion(_SYSTEM_PROMPT, state["raw_message"])
    return {"answer": answer, "escalated": False, "sources": []}
