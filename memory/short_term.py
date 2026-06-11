from __future__ import annotations
import structlog
from langchain_core.messages import HumanMessage, AIMessage

log = structlog.get_logger()


def add_to_history(short_term: list, user_msg: str, agent_msg: str) -> list:
    """Add a conversation turn to short-term memory."""
    updated = list(short_term)
    updated.append(HumanMessage(content=user_msg))
    updated.append(AIMessage(content=agent_msg))
    # Keep last 10 turns (20 messages) to avoid token overflow
    if len(updated) > 20:
        updated = updated[-20:]
    log.info("short_term_updated", turns=len(updated)//2)
    return updated


def format_history(short_term: list) -> str:
    """Format conversation history as a string for context injection."""
    if not short_term:
        return ""
    lines = []
    for msg in short_term:
        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
        lines.append(f"{role}: {msg.content[:200]}")
    return "\n".join(lines)
