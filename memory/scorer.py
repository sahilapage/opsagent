from __future__ import annotations
import structlog
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from rag.config import get_settings

log = structlog.get_logger()

SCORING_PROMPT = """Rate the importance of storing this memory on a scale of 0.0 to 1.0.

High importance (0.8-1.0): Personal facts, goals, preferences, technical stack, important decisions
Medium importance (0.5-0.7): Context about current tasks, recent questions
Low importance (0.0-0.4): Trivial questions, greetings, temporary context

Return ONLY a decimal number between 0.0 and 1.0, nothing else."""


def score_memory(content: str) -> float:
    s = get_settings()
    llm = ChatGroq(model=s.groq_model_fast, api_key=s.groq_api_key, temperature=0)
    try:
        response = llm.invoke([
            SystemMessage(content=SCORING_PROMPT),
            HumanMessage(content=content),
        ])
        score = float(response.content.strip())
        score = max(0.0, min(1.0, score))
        log.info("memory_scored", content=content[:50], score=score)
        return score
    except Exception as e:
        log.error("scoring_error", error=str(e))
        return 0.5


def should_store(content: str, threshold: float = 0.5) -> bool:
    score = score_memory(content)
    return score >= threshold
