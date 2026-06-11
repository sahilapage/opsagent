from __future__ import annotations
import structlog
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from rag.config import get_settings
from agents.state import AgentState

log = structlog.get_logger()

def get_llm():
    s = get_settings()
    return ChatGroq(model=s.groq_model_large, api_key=s.groq_api_key, temperature=0)

def analysis_node(state: AgentState) -> AgentState:
    try:
        llm = get_llm()
        messages = [
            SystemMessage(content="You are a precise data analysis assistant. Show your reasoning step by step. Be concise."),
            HumanMessage(content=state["task"]),
        ]
        response = llm.invoke(messages)
        log.info("analysis_node_done")
        return {
            **state,
            "results": state["results"] + [{"agent": "analysis", "output": response.content}],
            "final_answer": response.content,
        }
    except Exception as e:
        log.error("analysis_node_error", error=str(e))
        return {**state, "error": str(e)}
