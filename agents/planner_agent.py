from __future__ import annotations
import json
import structlog
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from rag.config import get_settings
from agents.state import AgentState

log = structlog.get_logger()

PLANNER_PROMPT = """You are a task planner for an AI agent system.
Your job is to decide if a task needs multiple agents working together.

Available agents:
- rag: search knowledge base / answer from documents
- analysis: data analysis, calculations, explanations
- browser: search web, scrape URLs
- action: send email, create calendar event, read Gmail, Google Drive
- github: GitHub issues, PRs, commits, auto-fix
- code: execute Python code, generate charts, run scripts
- general: general knowledge questions, personal questions, memory recall

STRICT RULES — set needs_planning to FALSE for:
- ANY question about the user themselves ("who am I", "what is my name", "what am I working on")
- Simple single questions answerable by one agent
- Greetings or conversational queries
- Questions about a single topic or service
- Memory or context questions

Set needs_planning to FALSE for:
- ANY single-service action (send email, create event, read emails, list files)
- Direct action requests that don't need data from another agent first

Set needs_planning to TRUE ONLY when ALL of these are true:
- Task EXPLICITLY mentions 3+ different services/tools
- Steps have clear sequential dependency (output of step 1 feeds step 2)
- Task uses words like "then", "after that", "and also", "followed by"

Examples:
"who am I" -> needs_planning: false (memory question, use general)
"what is my name" -> needs_planning: false (memory question)
"search web for X and email results" -> needs_planning: true (browser + action)
"analyze github issues then create a report and email it" -> needs_planning: true
"what is machine learning" -> needs_planning: false (single agent)
"show my calendar events" -> needs_planning: false (single agent)
"Send email to X with subject Y" -> needs_planning: false (single action agent task)
"Create a calendar event" -> needs_planning: false (single action agent task)
"Read my emails" -> needs_planning: false (single action agent task)

Return JSON only:
{
  "needs_planning": true or false,
  "steps": [],
  "reasoning": "brief reason"
}"""

def create_plan(task: str) -> dict:
    s = get_settings()
    llm = ChatGroq(model=s.groq_model_large, api_key=s.groq_api_key, temperature=0)
    try:
        response = llm.invoke([
            SystemMessage(content=PLANNER_PROMPT),
            HumanMessage(content=f"Task: {task}"),
        ])
        raw = response.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        return json.loads(raw)
    except Exception as e:
        log.error("planner_error", error=str(e))
        return {"needs_planning": False, "steps": [], "reasoning": ""}


def execute_step(step: dict, previous_results: list[str],
                 state: AgentState) -> str:
    """Execute a single plan step using the appropriate agent."""
    from agents.rag_agent import rag_node
    from agents.analysis_agent import analysis_node
    from agents.browser_agent import browser_node
    from agents.action_agent import action_node
    from agents.github_agent import github_node
    from agents.code_agent import code_node
    from agents.orchestrator import general_node

    agent_map = {
        "rag": rag_node,
        "analysis": analysis_node,
        "browser": browser_node,
        "action": action_node,
        "github": github_node,
        "code": code_node,
        "general": general_node,
    }

    agent_name = step["agent"]
    task = step["task"]

    # Inject previous results into the task if it depends on them
    if step.get("depends_on") and previous_results:
        dep_idx = step["depends_on"] - 1
        if dep_idx < len(previous_results):
            task = f"{task}\n\nContext from previous step:\n{previous_results[dep_idx][:500]}"

    # Create a sub-state for this step
    sub_state = {
        **state,
        "task": task,
        "plan": [agent_name],
        "results": [],
        "final_answer": None,
        "error": None,
    }

    node_fn = agent_map.get(agent_name)
    if not node_fn:
        return f"Unknown agent: {agent_name}"

    result_state = node_fn(sub_state)
    final = result_state.get("final_answer", "")
    if not final:
        return "No result"
    if isinstance(final, dict):
        return json.dumps(final)
    return str(final)


def planner_node(state: AgentState) -> AgentState:
    task = state["task"]
    plan = create_plan(task)

    if not plan.get("needs_planning") or not plan.get("steps"):
        log.info("planner_simple_task")
        return state  # Let router handle it normally

    steps = plan["steps"]
    log.info("planner_executing", steps=len(steps), reasoning=plan.get("reasoning", "")[:100])

    previous_results = []
    all_results = []

    for step in steps:
        # Validate step is a dict
        if not isinstance(step, dict):
            log.warning("planner_invalid_step", step=str(step)[:50])
            continue
        if "agent" not in step or "task" not in step:
            log.warning("planner_missing_fields", step=str(step)[:50])
            continue
        # Ensure step number exists
        if "step" not in step:
            step["step"] = steps.index(step) + 1

        log.info("planner_step", step=step["step"], agent=step["agent"])
        result = execute_step(step, previous_results, state)
        previous_results.append(result)
        all_results.append({
            "step": step["step"],
            "agent": step["agent"],
            "task": str(step.get("task", ""))[:100],
            "result": str(result)[:300],
        })

    # Synthesize final answer from all steps
    s = get_settings()
    llm = ChatGroq(model=s.groq_model_large, api_key=s.groq_api_key, temperature=0)

    synthesis_prompt = f"""Synthesize the results from this multi-step task into a clear final answer.

Original task: {task}

Steps completed:
{json.dumps(all_results, indent=2)}

Write a comprehensive final answer that combines all the results."""

    response = llm.invoke([HumanMessage(content=synthesis_prompt)])
    final_answer = response.content

    log.info("planner_complete", steps_completed=len(steps))
    return {
        **state,
        "results": state["results"] + all_results,
        "final_answer": final_answer,
        "plan": ["planner"],
    }
