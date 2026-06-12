from __future__ import annotations
import structlog
from rag.chain import answer as rag_answer
from agents.state import AgentState
from langsmith import traceable

log = structlog.get_logger()

@traceable(name="RAG Agent", run_type="retriever")
def rag_node(state: AgentState) -> AgentState:
    try:
        result = rag_answer(query=state["task"])
        log.info("rag_node_done", sources=len(result.sources))
        return {
            **state,
            "results": state["results"] + [{
                "agent": "rag",
                "output": result.answer,
                "sources": [s.metadata for s in result.sources]
            }],
            "final_answer": result.answer,
        }
    except Exception as e:
        log.error("rag_node_error", error=str(e))
        return {**state, "error": str(e)}
