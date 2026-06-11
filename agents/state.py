from __future__ import annotations
from typing import TypedDict, List, Optional, Annotated
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    task: str
    plan: List[str]
    current_step: int
    results: List[dict]
    final_answer: Optional[str]
    short_term: Annotated[list, add_messages]
    user_id: str
    session_id: str
    trace_id: str
    total_tokens: int
    error: Optional[str]
    memory_context: str
    history_context: str
    guardrail_passed: bool
    reflection_count: int