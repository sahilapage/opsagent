from __future__ import annotations
import json
import structlog
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from rag.config import get_settings
from agents.state import AgentState

log = structlog.get_logger()

MAX_REFLECTIONS = 2
QUALITY_THRESHOLD = 0.6

CRITIC_PROMPT = """You are a quality reviewer for an AI agent's responses.
Score this response and provide feedback.

Task: {task}
Agent used: {agent}
Response: {answer}

Evaluate on:
1. Accuracy — is the answer factually correct?
2. Completeness — does it fully address the question?
3. Clarity — is it easy to understand?
4. Relevance — does it stay on topic?

Return JSON only:
{{
  "score": 0.0 to 1.0,
  "passed": true or false,
  "feedback": "specific improvement suggestions",
  "strengths": "what was good"
}}"""

IMPROVE_PROMPT = """You are an expert AI assistant. Improve this response based on feedback.

Original task: {task}
Previous response: {answer}
Feedback: {feedback}

Write an improved, complete response that addresses all feedback points."""


def score_answer(task: str, answer: str, agent: str) -> dict:
    s = get_settings()
    llm = ChatGroq(model=s.groq_model_fast, api_key=s.groq_api_key, temperature=0)
    try:
        response = llm.invoke([
            HumanMessage(content=CRITIC_PROMPT.format(
                task=task, agent=agent, answer=answer[:1000]
            ))
        ])
        raw = response.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        result = json.loads(raw)
        result["passed"] = result.get("score", 0) >= QUALITY_THRESHOLD
        return result
    except Exception as e:
        log.error("critic_score_error", error=str(e))
        return {"score": 0.8, "passed": True, "feedback": "", "strengths": ""}


def improve_answer(task: str, answer: str, feedback: str) -> str:
    s = get_settings()
    llm = ChatGroq(model=s.groq_model_large, api_key=s.groq_api_key, temperature=0)
    response = llm.invoke([
        HumanMessage(content=IMPROVE_PROMPT.format(
            task=task, answer=answer[:1000], feedback=feedback
        ))
    ])
    return response.content


def critic_node(state: AgentState) -> AgentState:
    answer = state.get("final_answer", "")
    task = state.get("task", "")
    agent = state.get("plan", ["unknown"])[0]
    reflection_count = state.get("reflection_count", 0)

    if not answer or reflection_count >= MAX_REFLECTIONS:
        return state
    
    # Skip critic if memory context was injected — answer is already personalized
    if state.get("memory_context") and agent == "general":
        log.info("critic_skipped", reason="memory_context_present")
        return state

    # Skip critic for action/github/code agents — their output is factual
    if agent in {"action", "github", "code", "browser"}:
        log.info("critic_skipped", agent=agent)
        return state

    result = score_answer(task, answer, agent)
    log.info("critic_scored", score=result["score"], passed=result["passed"],
             reflection_count=reflection_count)

    if not result["passed"] and reflection_count < MAX_REFLECTIONS:
        log.info("critic_improving", feedback=result["feedback"][:100])
        improved = improve_answer(task, answer, result["feedback"])
        return {
            **state,
            "final_answer": improved,
            "reflection_count": reflection_count + 1,
        }

    return {**state, "reflection_count": reflection_count}
