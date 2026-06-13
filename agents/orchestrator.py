from __future__ import annotations
import uuid
import structlog
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from rag.config import get_settings
from agents.state import AgentState
from agents.rag_agent import rag_node
from agents.analysis_agent import analysis_node
from agents.browser_agent import browser_node
from agents.action_agent import action_node
from agents.github_agent import github_node
from agents.code_agent import code_node
from agents.guardrail_agent import guardrail_node
from agents.critic_agent import critic_node
from agents.planner_agent import planner_node
from langsmith import traceable


log = structlog.get_logger()


# ── LLM ───────────────────────────────────────────────────────────────────────

def get_llm_fast():
    s = get_settings()
    return ChatGroq(model=s.groq_model_fast, api_key=s.groq_api_key, temperature=0)


# ── Router ─────────────────────────────────────────────────────────────────────

ROUTER_PROMPT = """Classify the user query into exactly one category.

Categories:
- rag: questions explicitly about ingested documents, papers, research, "what does the paper say", "according to the document", topics that were likely uploaded
- analysis: math, calculations, data analysis, statistics, "how many", "calculate", "compute", economic analysis, ripple effects
- action: send email, read emails, Gmail, create/list calendar events, Google Calendar, list/read Drive files, Google Drive
- browser: search web, visit URL, find latest news, current scores, recent events, anything requiring real-time information, "latest", "current", "today", "recent", "live"
- general: general knowledge questions, factual world knowledge, history, sports, science, people, places, current events, anything not requiring a document lookup
- github: anything involving GitHub — issues, PRs, commits, branches, repo, code review, auto-fix, workflow runs, search code in repo, get file from repo
- code: run code, execute python, calculate with code, plot a chart, generate a script, "run this", "execute", "compute using code", "write a script"

Rules:
- Reply with ONLY the single category word
- No punctuation, no explanation, no other words
- Use "general" for world knowledge questions (who is X, what is Y, history, sports, geography)
- Use "rag" ONLY when the question is likely about an uploaded document or research paper
- Default to "general" if unsure between rag and general
- If the task contains a full URL (starts with http:// or https://), ALWAYS route to browser
- CRITICAL: anything mentioning "github", "repo", "repository", "issue", "PR", "pull request", "branch", "commit" -> github
- CRITICAL: anything mentioning "email", "gmail", "calendar", "drive", "send email", "read email" -> action

Examples:
"What does the paper say about X?" -> rag
"Who owns the IPL?" -> general
"What is quantum computing?" -> general
"Calculate 10% of 500" -> analysis
"Send an email to John" -> action
"Read my emails" -> action
"List my Gmail inbox" -> action
"List my Google Drive files" -> action
"Create a calendar event" -> action
"Show my calendar" -> action
"Search the web for latest AI news" -> browser
"What is the latest test match score?" -> browser
"Tell me about latest cricket match" -> browser
"What happened in the news today?" -> browser
"Latest score of India vs Australia" -> browser
"Scrape https://arxiv.org/abs/2106.09685 and summarize" -> browser
"List my GitHub issues" -> github
"Create a GitHub issue" -> github
"Create a branch in my repo" -> github
"Create a github branch called X from main" -> github
"What PRs are open in my repo?" -> github
"Suggest a fix for issue #5" -> github
"Auto fix GitHub issue number 1" -> github
"How many github repos do I have?" -> github
"Fix issue #1 automatically" -> github
"Create a PR to fix issue 1" -> github
"Review PR number 2" -> github
"Show repo health" -> github
"List commits in my repo" -> github
"Search code in my github repo for X" -> github
"Get the file README.md from my github repo" -> github
"Get file contents from repo" -> github
"Show github workflow runs" -> github
"Run a Python script to calculate fibonacci numbers" -> code
"Execute code to plot a sine wave" -> code
"Write and run a script to sort this data" -> code
"Calculate compound interest with code" -> code
"Hello how are you" -> general"""



def router_node(state: AgentState) -> AgentState:
    llm = get_llm_fast()
    messages = [
        SystemMessage(content=ROUTER_PROMPT),
        HumanMessage(content=f"Query: {state['task']}"),
    ]
    response = llm.invoke(messages)
    raw = response.content.strip().lower()

    valid = {"rag", "analysis", "action", "browser", "general", "github", "code"}
    category = "general"
    for word in raw.split():
        cleaned = word.strip(".,!?:;\"'")
        if cleaned in valid:
            category = cleaned
            break

    log.info("router_decision", task=state["task"][:60], raw=raw, category=category)
    return {**state, "plan": [category], "current_step": 0}


# ── General node ───────────────────────────────────────────────────────────────

# def general_node(state: AgentState) -> AgentState:
#     try:
#         s = get_settings()
#         llm = ChatGroq(model=s.groq_model_large, api_key=s.groq_api_key, temperature=0)
#         messages = [
#             SystemMessage(content="You are a helpful business operations assistant. Be concise and accurate."),
#             HumanMessage(content=state["task"]),
#         ]
#         response = llm.invoke(messages)
#         return {
#             **state,
#             "results": state["results"] + [{"agent": "general", "output": response.content}],
#             "final_answer": response.content,
#         }
#     except Exception as e:
#         log.error("general_node_error", error=str(e))
#         return {**state, "error": str(e)}

# def general_node(state: AgentState) -> AgentState:
#     try:
#         s = get_settings()
#         llm = ChatGroq(model=s.groq_model_large, api_key=s.groq_api_key, temperature=0)
        
#         system = "You are a helpful business operations assistant. Be concise and accurate."
#         if state.get("memory_context"):
#             system += f"\n\nRelevant context about the user:\n{state['memory_context']}"
        
#         messages = [
#             SystemMessage(content=system),
#             HumanMessage(content=state["task"]),
#         ]
#         response = llm.invoke(messages)
#         return {
#             **state,
#             "results": state["results"] + [{"agent": "general", "output": response.content}],
#             "final_answer": response.content,
#         }
#     except Exception as e:
#         log.error("general_node_error", error=str(e))
#         return {**state, "error": str(e)}

def general_node(state: AgentState) -> AgentState:
    try:
        s = get_settings()
        llm = ChatGroq(model=s.groq_model_large, api_key=s.groq_api_key, temperature=0)

        system = "You are a helpful business operations assistant. Be concise and accurate."
        if state.get("memory_context"):
            system += f"\n\nWhat you know about the user:\n{state['memory_context']}"
        if state.get("history_context"):
            system += f"\n\nRecent conversation:\n{state['history_context']}"

        messages = [
            SystemMessage(content=system),
            HumanMessage(content=state["task"]),
        ]
        response = llm.invoke(messages)
        return {
            **state,
            "results": state["results"] + [{"agent": "general", "output": response.content}],
            "final_answer": response.content,
        }
    except Exception as e:
        log.error("general_node_error", error=str(e))
        return {**state, "error": str(e)}


# ── Routing function ───────────────────────────────────────────────────────────

def route_to_agent(state: AgentState) -> str:
    plan = state.get("plan", ["general"])
    return plan[0] if plan else "general"


# ── Build graph ────────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(AgentState)

    # Add all nodes
    graph.add_node("guardrail", guardrail_node)
    graph.add_node("planner", planner_node)
    graph.add_node("router", router_node)
    graph.add_node("rag", rag_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("action", action_node)
    graph.add_node("browser", browser_node)
    graph.add_node("general", general_node)
    graph.add_node("github", github_node)
    graph.add_node("code", code_node)
    graph.add_node("critic", critic_node)

    # Entry point is guardrail
    graph.set_entry_point("guardrail")

    # Guardrail → planner or END if blocked
    def guardrail_route(state: AgentState) -> str:
        if state.get("guardrail_passed", True):
            return "planner"
        return "blocked"

    graph.add_node("blocked", lambda s: s)
    graph.add_conditional_edges(
        "guardrail",
        guardrail_route,
        {"planner": "planner", "blocked": "blocked"}
    )
    graph.add_edge("blocked", END)

    # Planner → router (if simple) or handles multi-step itself
    graph.add_conditional_edges(
        "planner",
        lambda s: END if s.get("plan") == ["planner"] else "router",
        {"router": "router", END: END}
    )

    # Router → agents
    graph.add_conditional_edges(
        "router",
        route_to_agent,
        {
            "rag": "rag",
            "analysis": "analysis",
            "action": "action",
            "browser": "browser",
            "general": "general",
            "github": "github",
            "code": "code",
        }
    )

    # All agents → critic
    for agent in ["rag", "analysis", "action", "browser", "general", "github", "code"]:
        graph.add_edge(agent, "critic")

    # Critic → END
    graph.add_edge("critic", END)

    return graph.compile()


# ── Singleton ──────────────────────────────────────────────────────────────────

_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ── Public API ─────────────────────────────────────────────────────────────────

# def run_agent(task: str, user_id: str = "default") -> dict:
#     graph = get_graph()
#     initial_state: AgentState = {
#         "task": task,
#         "plan": [],
#         "current_step": 0,
#         "results": [],
#         "final_answer": None,
#         "short_term": [],
#         "user_id": user_id,
#         "trace_id": str(uuid.uuid4()),
#         "total_tokens": 0,
#         "error": None,
#     }
#     final_state = graph.invoke(initial_state)
#     return {
#         "answer": final_state.get("final_answer"),
#         "agent_used": final_state.get("plan", ["unknown"])[0],
#         "trace_id": final_state.get("trace_id"),
#         "error": final_state.get("error"),
#     }

# def run_agent(task: str, user_id: str = "default") -> dict:
#     from memory.long_term import retrieve_memories, store_memory
#     from memory.short_term import add_to_history

#     # Inject relevant long-term memories into the task
#     memories = retrieve_memories(user_id, task, top_k=3)
#     enriched_task = task
#     if memories:
#         memory_context = "\n".join(f"- {m}" for m in memories)
#         enriched_task = f"{task}\n\n[Relevant context from memory:\n{memory_context}]"

#     graph = get_graph()
#     initial_state: AgentState = {
#         "task": enriched_task,
#         "plan": [],
#         "current_step": 0,
#         "results": [],
#         "final_answer": None,
#         "short_term": [],
#         "user_id": user_id,
#         "trace_id": str(uuid.uuid4()),
#         "total_tokens": 0,
#         "error": None,
#     }
#     final_state = graph.invoke(initial_state)

#     # Store this interaction in long-term memory
#     if final_state.get("final_answer"):
#         store_memory(
#             user_id=user_id,
#             content=f"User asked: {task[:200]}",
#             memory_type="context"
#         )

#     return {
#         "answer": final_state.get("final_answer"),
#         "agent_used": final_state.get("plan", ["unknown"])[0],
#         "trace_id": final_state.get("trace_id"),
#         "error": final_state.get("error"),
#     }

# def run_agent(task: str, user_id: str = "default") -> dict:
#     from memory.long_term import retrieve_memories, store_memory

#     # Retrieve relevant memories
#     # memories = retrieve_memories(user_id, task, top_k=3)
#     memories = retrieve_memories(user_id, task, top_k=5)
    
#     memory_context = ""
#     if memories:
#         memory_context = "\n".join(f"- {m}" for m in memories)

#     graph = get_graph()
#     initial_state: AgentState = {
#         "task": task,                    # original task for routing
#         "plan": [],
#         "current_step": 0,
#         "results": [],
#         "final_answer": None,
#         "short_term": [],
#         "user_id": user_id,
#         "trace_id": str(uuid.uuid4()),
#         "total_tokens": 0,
#         "error": None,
#         "memory_context": memory_context,  # separate field
#     }
#     final_state = graph.invoke(initial_state)

#     # if final_state.get("final_answer"):
#     #     store_memory(
#     #         user_id=user_id,
#     #         content=f"User asked: {task[:200]}",
#     #         memory_type="context"
#     #     )

#     if final_state.get("final_answer"):
#         final_answer = final_state.get("final_answer", "")
#         # Store richer context — both question and answer
#         store_memory(
#             user_id=user_id,
#             content=f"User asked: {task[:200]}. Agent answered: {final_answer[:200]}",
#             memory_type="context"
#         )

#     return {
#         "answer": final_state.get("final_answer"),
#         "agent_used": final_state.get("plan", ["unknown"])[0],
#         "trace_id": final_state.get("trace_id"),
#         "error": final_state.get("error"),
#     }

# def run_agent(task: str, user_id: str = "default") -> dict:
#     from memory.long_term import retrieve_memories, store_memory
#     from memory.extractor import extract_memories
#     from memory.scorer import should_store

#     # 1. Retrieve relevant long-term memories
#     memories = retrieve_memories(user_id, task, top_k=5)
#     memory_context = "\n".join(f"- {m}" for m in memories) if memories else ""

#     graph = get_graph()
#     initial_state: AgentState = {
#         "task": task,
#         "plan": [],
#         "current_step": 0,
#         "results": [],
#         "final_answer": None,
#         "short_term": [],
#         "user_id": user_id,
#         "trace_id": str(uuid.uuid4()),
#         "total_tokens": 0,
#         "error": None,
#         "memory_context": memory_context,
#     }
#     final_state = graph.invoke(initial_state)
#     final_answer = final_state.get("final_answer", "")

#     # 2. Auto-extract facts from this conversation
#     if final_answer:
#         extracted = extract_memories(task, final_answer)
#         for fact in extracted:
#             if should_store(fact, threshold=0.5):
#                 store_memory(
#                     user_id=user_id,
#                     content=fact,
#                     memory_type="fact",
#                     importance=0.8,
#                 )

#         # 3. Store conversation context with lower importance
#         if should_store(f"User asked: {task}", threshold=0.3):
#             store_memory(
#                 user_id=user_id,
#                 content=f"User asked: {task[:200]}",
#                 memory_type="context",
#                 importance=0.3,
#             )

#     return {
#         "answer": final_answer,
#         "agent_used": final_state.get("plan", ["unknown"])[0],
#         "trace_id": final_state.get("trace_id"),
#         "error": final_state.get("error"),
#     }

# def run_agent(task: str, user_id: str = "default",
#               session_id: str = None) -> dict:
#     import uuid as _uuid
#     from memory.long_term import retrieve_memories, store_memory
#     from memory.extractor import extract_memories
#     from memory.scorer import should_store
#     from memory.conversation import store_turn, get_recent_history, format_history_for_context

#     # Generate session_id if not provided
#     if not session_id:
#         session_id = str(_uuid.uuid4())

#     # 1. Retrieve relevant long-term memories
#     memories = retrieve_memories(user_id, task, top_k=5)
#     memory_context = "\n".join(f"- {m}" for m in memories) if memories else ""

#     # 2. Retrieve recent conversation history
#     recent_history = get_recent_history(user_id, turns=6)
#     history_context = format_history_for_context(recent_history)

#     # 3. Store user turn
#     store_turn(user_id, session_id, "user", task)

#     graph = get_graph()
#     initial_state: AgentState = {
#         "task": task,
#         "plan": [],
#         "current_step": 0,
#         "results": [],
#         "final_answer": None,
#         "short_term": [],
#         "user_id": user_id,
#         "trace_id": str(_uuid.uuid4()),
#         "total_tokens": 0,
#         "error": None,
#         "memory_context": memory_context,
#         "history_context": history_context,
#     }
#     final_state = graph.invoke(initial_state)
#     final_answer = final_state.get("final_answer", "")
#     plan = final_state.get("plan", [])
    agent_used = plan[0] if plan else "blocked"

#     # 4. Store assistant turn
#     if final_answer:
#         store_turn(user_id, session_id, "assistant", final_answer, agent_used)

#     # 5. Auto-extract facts
#     if final_answer:
#         extracted = extract_memories(task, final_answer)
#         for fact in extracted:
#             if should_store(fact, threshold=0.5):
#                 store_memory(
#                     user_id=user_id,
#                     content=fact,
#                     memory_type="fact",
#                     importance=0.8,
#                 )

#         if should_store(f"User asked: {task}", threshold=0.3):
#             store_memory(
#                 user_id=user_id,
#                 content=f"User asked: {task[:200]}",
#                 memory_type="context",
#                 importance=0.3,
#             )

#     return {
#         "answer": final_answer,
#         "agent_used": agent_used,
#         "trace_id": final_state.get("trace_id"),
#         "session_id": session_id,
#         "error": final_state.get("error"),
#     }

@traceable(name="OpsAgent", run_type="chain")
def run_agent(task: str, user_id: str = "default",
              session_id: str = None) -> dict:
    import uuid as _uuid
    from memory.long_term import retrieve_memories, get_top_memories
    from memory.conversation import store_turn, get_recent_history, format_history_for_context

    if not session_id:
        session_id = str(_uuid.uuid4())

    # Retrieve only — fast DB queries
    semantic_memories = retrieve_memories(user_id, task, top_k=5)
    top_facts = get_top_memories(user_id, top_k=5)
    all_memories = list(dict.fromkeys(semantic_memories + top_facts))
    memory_context = "\n".join(f"- {m}" for m in all_memories[:10]) if all_memories else ""
    log.info("memory_debug", count=len(all_memories), context_preview=memory_context[:200])
    recent_history = get_recent_history(user_id, turns=6)
    history_context = format_history_for_context(recent_history)
    store_turn(user_id, session_id, "user", task)

    graph = get_graph()
    initial_state: AgentState = {
        "task": task,
        "plan": [],
        "current_step": 0,
        "results": [],
        "final_answer": None,
        "short_term": [],
        "user_id": user_id,
        "trace_id": str(_uuid.uuid4()),
        "total_tokens": 0,
        "error": None,
        "memory_context": memory_context,
        "history_context": history_context,
    }

    final_state = graph.invoke(initial_state)
    final_answer = final_state.get("final_answer", "")
    plan = final_state.get("plan", [])
    log.info("run_agent_complete", plan=plan, plan_type=type(plan).__name__, final_answer_len=len(final_answer or ""))
    if not isinstance(plan, list):
        plan = []
    agent_used = plan[0] if plan else "blocked"

    if final_answer:
        store_turn(user_id, session_id, "assistant", final_answer, agent_used)

    return {
        "answer": final_answer,
        "agent_used": agent_used,
        "trace_id": final_state.get("trace_id"),
        "session_id": session_id,
        "error": final_state.get("error"),
    }