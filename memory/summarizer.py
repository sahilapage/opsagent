from __future__ import annotations
import structlog
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from rag.config import get_settings
from memory.long_term import list_memories

log = structlog.get_logger()

SUMMARY_PROMPT = """You are a memory summarizer. Given a list of facts and context about a user, 
create a concise, well-organized summary of everything known about them.

Format it as:
- Personal: (name, location, background)
- Projects: (what they are building)
- Tech Stack: (tools and technologies)
- Goals: (what they want to achieve)
- Preferences: (how they like to work)
- Recent Activity: (what they have been doing lately)

Only include sections where you have actual information. Be concise."""


def summarize_memories(user_id: str) -> str:
    memories = list_memories(user_id)
    if not memories:
        return f"No memories found for user: {user_id}"

    # Format memories for the LLM
    facts = [m for m in memories if m["type"] == "fact"]
    context = [m for m in memories if m["type"] == "context"]

    memory_text = "FACTS:\n"
    memory_text += "\n".join(f"- {m['content']}" for m in facts)
    memory_text += "\n\nRECENT ACTIVITY:\n"
    memory_text += "\n".join(f"- {m['content']}" for m in context[-5:])

    s = get_settings()
    llm = ChatGroq(model=s.groq_model_large, api_key=s.groq_api_key, temperature=0)

    response = llm.invoke([
        SystemMessage(content=SUMMARY_PROMPT),
        HumanMessage(content=memory_text),
    ])

    log.info("memory_summarized", user_id=user_id, memory_count=len(memories))
    return response.content
