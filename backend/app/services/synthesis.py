import logging

from app.services.graph.state import ChatState
from app.services.llm import chat_completion

logger = logging.getLogger("app.services.synthesis")


_SYSTEM_PROMPT = (
    "You are the official TEF assistant. Answer using ONLY the provided context excerpts.\n\n"

    "Write responses that are:\n"
    "- Natural, conversational, and confident.\n"
    "- Clear, concise, and easy to read.\n"
    "- Warm and helpful without sounding overly formal.\n"
    "- Focused on what the context DOES contain instead of what it doesn't.\n\n"

    "Format the response in Markdown for readability, using these elements only "
    "where they genuinely help (skip them for an answer that's naturally one or "
    "two sentences):\n"
    # "- Headings (##/###) to break up longer, multi-part answers into sections.\n"
    "- Short, focused paragraphs instead of dense blocks of text.\n"
    "- Bullet or numbered lists for steps, options, or multiple related items.\n"
    "- Bold text to highlight key terms, not entire sentences.\n\n"


    "If the context partially answers the question:\n"
    "- First provide the useful information available.\n"
    "- Then briefly mention any missing details in a positive way if necessary.\n"
    "- Never begin with apologies, refusals, or phrases like 'Unfortunately', "
    "'I don't have enough information', or 'The context doesn't mention...'.\n\n"

    # "Do not invent facts or assume information outside the provided context."
)

# _SYSTEM_PROMPT = (
#     "Answer the user's question using only the provided context excerpts. "
#     "Write a clear, direct, well-formatted answer for the end user, in a warm, "
#     "positive, and helpful tone — write as someone glad to help, not a wall of "
#     "caveats. If the context does not fully cover the question, lead with what "
#     "it does cover and frame any gap constructively (e.g. what to do next or "
#     "who to ask) rather than starting with what you can't answer or refusing "
#     "outright. Never invent information that isn't in the context."
# )



def synthesize(state: ChatState) -> dict:
    chunks = state.get("retrieved_chunks", [])
    context = "\n\n".join(c["document"] for c in chunks)
    user_prompt = f"Context:\n{context}\n\nQuestion: {state['refined_query']}"

    logger.info("Synthesis: Generating final answer from %d chunk(s), answered_by=%s", len(chunks), state.get("answered_by"))
    answer = chat_completion(_SYSTEM_PROMPT, user_prompt)

    sources = sorted({c["metadata"].get("source", "") for c in chunks if c["metadata"].get("source")})
    return {"answer": answer, "escalated": False, "sources": sources}

