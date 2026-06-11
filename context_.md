# OpsAgent — Full Project Context for LLM
# Feed this entire file at the start of every new chat session.
# Last updated: June 2026

---

## WHAT YOU ARE HELPING BUILD

OpsAgent is a production-grade autonomous business operations agent.
It monitors data, retrieves knowledge, takes real-world actions (email, calendar, tickets),
runs data analysis, browses the web, executes code, manages GitHub repos,
runs scheduled autonomous tasks, and responds via voice.
It is built as a portfolio project to land a well-paying AI/ML internship.

The builder is a student in India. Budget: zero. All LLMs are FREE.

---

## PRIMARY LLM — GROQ (FREE TIER)

All LLM calls in this project use Groq's free API.
Never suggest OpenAI, Anthropic, or any paid LLM API.

```python
from langchain_groq import ChatGroq

llm = ChatGroq(
    model="llama-3.3-70b-versatile",   # best reasoning, use for orchestrator
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0,
)

# For faster / lighter tasks use:
# model="llama-3.1-8b-instant"         # fast, cheap on rate limits
# model="mixtral-8x7b-32768"           # long context tasks
```

Groq free tier limits: ~14,400 requests/day, 6000 tokens/min on 70B model.
Design agents to be token-efficient. Use smaller models for simple routing decisions.

---

## TECH STACK (COMPLETE)

| Layer             | Tool / Library                        |
|-------------------|---------------------------------------|
| LLM API           | Groq (free) — llama-3.3-70b           |
| Local LLM backup  | Ollama — llama3.2, qwen2.5-coder      |
| Agent framework   | LangGraph                             |
| LLM toolkit       | LangChain + langchain-groq            |
| Vector DB         | Qdrant (Docker)                       |
| Embeddings        | fastembed (mixedbread-ai/mxbai-embed-large-v1, 1024d) |
| Reranking         | cross-encoder/ms-marco-MiniLM-L-6-v2 (local, no API) |
| SQL DB            | PostgreSQL + pgvector (Docker)        |
| MCP protocol      | mcp[cli] Python SDK                   |
| API backend       | FastAPI + Uvicorn                     |
| WebSocket         | FastAPI WebSocket                     |
| Frontend          | React + Vite                          |
| Browser agent     | Playwright (async) + Serper API       |
| STT               | OpenAI Whisper (local, free)          |
| TTS               | ElevenLabs API (free tier)            |
| Evals             | RAGAS (separate eval_venv) + LangSmith|
| Observability     | LangSmith tracing (@traceable)        |
| Containerisation  | Docker + Docker Compose               |
| CI/CD             | GitHub Actions                        |
| Deployment        | Railway (free tier)                   |
| Scheduling        | APScheduler                           |
| GitHub integration| PyGithub                              |
| Code execution    | subprocess (sandboxed)                |
| Slack integration | slack-sdk                             |

---

## FULL REPO STRUCTURE

```
opsagent/
├── agents/
│   ├── __init__.py
│   ├── state.py              # AgentState TypedDict
│   ├── orchestrator.py       # LangGraph state machine — main brain
│   ├── rag_agent.py          # retrieves from vector DB ✅
│   ├── browser_agent.py      # Playwright + Serper web search ✅
│   ├── action_agent.py       # emails, calendar, drive via Google API ✅
│   ├── analysis_agent.py     # LLM analysis ✅
│   ├── code_agent.py         # sandboxed Python execution ← NEW
│   ├── github_agent.py       # GitHub issues, PRs, commits ← NEW
│   ├── sql_agent.py          # natural language → SQL → results ← NEW
│   ├── slack_agent.py        # Slack read/write/alert ← NEW
│   ├── planner_agent.py      # multi-agent coordination ← NEW
│   ├── critic_agent.py       # reflection + self-improvement loop ← NEW
│   └── guardrail_agent.py    # prompt injection detection ← NEW
│
├── mcp_servers/
│   ├── server.py             # custom MCP server (properly wired) ✅
│   └── tools/
│       ├── rag_tool.py       ✅
│       ├── analysis_tool.py  ✅
│       └── memory_tool.py    ✅
│
├── rag/
│   ├── __init__.py
│   ├── config.py             ✅
│   ├── models.py             ✅
│   ├── loaders.py            ✅
│   ├── chunker.py            ✅
│   ├── store.py              ✅
│   ├── reranker.py           ✅ (local ms-marco)
│   ├── retriever.py          ✅
│   ├── chain.py              ✅ (+ streaming version)
│   └── ingest.py             ✅
│
├── memory/
│   ├── __init__.py           ✅
│   ├── short_term.py         ✅
│   ├── long_term.py          ✅ (pgvector + decay + dedup)
│   ├── extractor.py          ✅ (auto-extract facts)
│   ├── scorer.py             ✅ (importance scoring)
│   ├── summarizer.py         ✅ (memory summary)
│   └── conversation.py       ✅ (cross-session history)
│
├── voice/
│   ├── stt.py                ✅ (Whisper)
│   └── tts.py                ✅ (ElevenLabs eleven_flash_v2_5)
│
├── scheduler/
│   └── jobs.py               ← NEW (APScheduler cron jobs)
│
├── api/
│   ├── __init__.py
│   ├── main.py               ✅ (+ streaming + HITL endpoints)
│   └── ws.py                 ✅ (WebSocket voice)
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx           ← NEW (minimal but real)
│   │   ├── components/
│   │   │   ├── ChatWindow.jsx    ← NEW
│   │   │   ├── VoiceButton.jsx   ← NEW
│   │   │   └── TracePanel.jsx    ← NEW
│   └── package.json
│
├── evals/
│   ├── rag_eval.py           ✅ (RAGAS in separate eval_venv)
│   ├── test_cases.json       ✅ (20 Q&A pairs)
│   └── cost_tracker.py       ✅
│
├── infra/
│   ├── docker-compose.yml    ✅ (Qdrant + PostgreSQL)
│   ├── Dockerfile            ← NEW
│   └── .github/
│       └── workflows/
│           └── ci.yml        ← NEW (eval gate → deploy)
│
├── docs/
│   └── postmortem.md         ← NEW (real failure + fix writeup)
│
├── voice_query.sh            ✅
├── auth_google.py            ✅
├── credentials.json          ✅
├── token.json                ✅
├── .env                      ✅
├── .env.example              ← NEW
├── requirements.txt          ✅
└── README.md                 ← NEW (architecture + setup + demo)
```

---

## ENVIRONMENT VARIABLES (.env)

```env
# === LLM ===
GROQ_API_KEY=gsk_...
GROQ_MODEL_LARGE=llama-3.3-70b-versatile
GROQ_MODEL_FAST=llama-3.1-8b-instant

# === VECTOR DB ===
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=opsagent_knowledge

# === POSTGRES ===
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=opsagent
POSTGRES_USER=opsagent
POSTGRES_PASSWORD=opsagent_secret
DATABASE_URL=postgresql://opsagent:opsagent_secret@localhost:5432/opsagent

# === EMBEDDINGS ===
EMBED_MODEL=mixedbread-ai/mxbai-embed-large-v1
EMBED_DIM=1024

# === GOOGLE APIs ===
GMAIL_MCP_URL=https://gmailmcp.googleapis.com/mcp/v1
GDRIVE_MCP_URL=https://drivemcp.googleapis.com/mcp/v1
GCALENDAR_MCP_URL=https://calendarmcp.googleapis.com/mcp/v1

# === VOICE ===
ELEVENLABS_API_KEY=sk_...
ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
WHISPER_MODEL=base

# === OBSERVABILITY ===
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_...
LANGCHAIN_PROJECT=opsagent

# === SEARCH ===
SERPER_API_KEY=...

# === GITHUB ===
GITHUB_TOKEN=ghp_...
GITHUB_DEFAULT_REPO=username/reponame

# === SLACK ===
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C...

# === JIRA ===
JIRA_URL=https://yoursite.atlassian.net
JIRA_EMAIL=your@email.com
JIRA_API_TOKEN=...

# === API ===
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=change_this_in_production

# === EVALS ===
RAGAS_MIN_FAITHFULNESS=0.85
RAGAS_MIN_RELEVANCY=0.80
```

---

## CURRENT STATUS

[x] Phase 0 — Repo setup, Docker Compose (Qdrant + PostgreSQL), .env
[x] Phase 1 — RAG pipeline: ingest → 1024d embed → hybrid search → rerank → answer
[x] Phase 2 — Multi-agent orchestration with LangGraph (router + 5 agents)
[x] Phase 3 — MCP: custom server + Gmail + Google Calendar + Google Drive
[x] Phase 4 — Browser agent: Playwright + Serper web search
[x] Phase 5 — Memory: short-term + long-term pgvector + auto-extraction + conversation history
[x] Phase 6 — Voice: Whisper STT + ElevenLabs TTS + WebSocket + voice_query.sh
[ ] Phase 7 — Evals: RAGAS suite (eval_venv ready, need token reset to complete)
[ ] Phase 8 — New agents: GitHub, Code execution, SQL, Slack, Planner, Critic, Guardrail
[ ] Phase 9 — Production improvements: HITL, streaming, LangSmith tracing, MCP fix
[ ] Phase 10 — Frontend: React chat UI with streaming + voice button + trace panel
[ ] Phase 11 — Scheduler: APScheduler autonomous morning report
[ ] Phase 12 — Deploy: Dockerfile + CI/CD + Railway

---

## WHAT IS ALREADY WORKING (TESTED)

RAG Pipeline:
- PDF/CSV/URL ingestion → 1024-dim mxbai embeddings → Qdrant hybrid search (dense + BM25 + RRF)
- Local ms-marco reranker (no API limits)
- Grounded answers with citations from ingested documents

Agent Orchestrator (LangGraph):
- Router using llama-3.1-8b-instant for classification
- 5 agents: RAG, analysis, browser, action, general
- Correct routing for document questions, math, web search, email/calendar, world knowledge
- Memory injection into every query

Memory System:
- Auto-extracts facts from every conversation
- Importance scoring (0-1) before storing
- Deduplication (cosine similarity threshold 0.95)
- Memory decay based on importance + access frequency
- Cross-session conversation history in PostgreSQL
- Memory summary endpoint

Action Agent (Google APIs):
- Gmail: read unread, filter by inbox/category, send emails ✅ TESTED (emails delivered)
- Google Calendar: list events, create events ✅ TESTED
- Google Drive: list files ✅ TESTED

Browser Agent:
- Serper API for web search ✅
- Playwright for URL scraping ✅
- Synthesizes answers from live web content ✅

Voice:
- Whisper base model STT ✅
- ElevenLabs eleven_flash_v2_5 TTS ✅
- voice_query.sh helper script ✅
- Full pipeline: record → transcribe → agent → speak ✅

---

## ARCHITECTURE — HOW IT ALL CONNECTS

```
User (voice or text)
        │
        ▼
  FastAPI backend (api/main.py)
        │
        ├── /query          → direct RAG
        ├── /agent          → full orchestrated pipeline
        ├── /stream         → streaming SSE (TODO)
        ├── /voice/*        → STT + agent + TTS
        ├── /memory/*       → memory CRUD + summary
        ├── /conversation/* → session history
        └── /eval/*         → RAGAS eval endpoints
        │
        ▼
  LangGraph Orchestrator
  (agents/orchestrator.py)
        │
        │  reads AgentState + memory context + conversation history
        │  runs guardrail check first
        │
  ┌─────┴──────────────────────────────────────┐
  │          Router (llama-3.1-8b-instant)      │
  └──┬──────┬──────┬──────┬──────┬──────┬───────┘
     │      │      │      │      │      │
     ▼      ▼      ▼      ▼      ▼      ▼
   RAG   Analysis Browser Action GitHub  SQL
   agent  agent   agent   agent  agent  agent
                              │
                         ┌────┴────┐
                         │  Planner│ (multi-step)
                         └────┬────┘
                    calls multiple agents in sequence
     │
     ▼
  Critic agent (reflection loop)
  scores answer, retries if < threshold
     │
     ▼
  Memory layer
  (auto-extract facts, store conversation, inject context)
```

---

## LANGGRAPH STATE SCHEMA

```python
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
    hitl_required: bool          # NEW: flag for human approval
    hitl_action: Optional[str]   # NEW: what action needs approval
    reflection_count: int         # NEW: how many times critic retried
    guardrail_passed: bool        # NEW: injection detection result
```

---

## NEW AGENTS TO BUILD (Phases 8-11)

### Phase 8A — GitHub Agent
```python
# agents/github_agent.py
# Uses: PyGithub (free)
# Can: list issues, create issues, read repo, suggest fixes, create PRs
# Router keywords: "github", "issue", "PR", "pull request", "repo", "commit"
```

### Phase 8B — Code Execution Agent
```python
# agents/code_agent.py
# Uses: subprocess (sandboxed), RestrictedPython
# Can: generate Python → execute → return results/plots/errors → retry
# Router keywords: "run", "execute", "calculate", "plot", "chart", "compute"
```

### Phase 8C — SQL Agent
```python
# agents/sql_agent.py
# Uses: existing PostgreSQL, SQLAlchemy
# Can: natural language → SQL → execute → return table → explain
# Router keywords: "database", "query", "SQL", "records", "table", "users"
```

### Phase 8D — Slack Agent
```python
# agents/slack_agent.py
# Uses: slack-sdk (free)
# Can: read channels, post messages, DM users, alert on anomalies
# Router keywords: "slack", "channel", "message", "post", "notify team"
```

### Phase 8E — Planner Agent
```python
# agents/planner_agent.py
# Uses: LangGraph subgraph
# Can: decompose complex tasks into steps, call multiple agents in sequence
# Triggered: when task requires multiple agents
# Example: "Analyze GitHub issues, summarize findings, email the team"
```

### Phase 8F — Critic Agent (Reflection Loop)
```python
# agents/critic_agent.py
# Uses: llama-3.1-8b-instant (fast scoring)
# Can: score answer quality 0-1, trigger retry with feedback if < 0.7
# Max retries: 2 (to avoid infinite loops)
```

### Phase 8G — Guardrail Agent
```python
# agents/guardrail_agent.py
# Uses: llama-3.1-8b-instant
# Can: detect prompt injection, jailbreak attempts, harmful requests
# Blocks: "ignore previous instructions", "delete all files", etc.
# Runs BEFORE router on every query
```

### Phase 8H — Jira Agent
```python
# agents/jira_agent.py
# Uses: jira Python SDK (free cloud tier)
# Can: create tickets, update status, assign issues, add comments
# Router keywords: "jira", "ticket", "bug", "story", "sprint"
```

---

## PRODUCTION IMPROVEMENTS (Phase 9)

### A. Human-in-the-Loop (HITL)
```python
# In action_agent.py before sending email/creating event:
# Use LangGraph interrupt() to pause and ask for confirmation
# State flag: hitl_required=True, hitl_action="Send email to X"
# Resume endpoint: POST /agent/approve/{trace_id}
```

### B. Streaming Responses
```python
# New endpoint: GET /stream?task=...&user_id=...
# Uses FastAPI StreamingResponse + SSE
# chain.py gets a stream=True mode
# Frontend consumes as EventSource
```

### C. LangSmith Tracing (properly wired)
```python
# Add @traceable to run_agent, every agent node
# Set LANGCHAIN_TRACING_V2=true (already in .env)
# Every call visible at smith.langchain.com
```

### D. Fix MCP (properly wired)
```python
# action_agent.py calls mcp_servers/server.py via MCP client protocol
# Not direct Google API calls
# Makes MCP claim real and demonstrable
```

---

## FRONTEND (Phase 10)

Minimal but real React UI:
- Chat window with message history
- Streaming token display (SSE)
- Voice button (record → send → play response)
- Agent indicator (shows which agent handled query)
- Memory panel (shows what agent knows about you)
- Trace panel (LangSmith trace link per response)

---

## SCHEDULER (Phase 11)

```python
# scheduler/jobs.py
# APScheduler with AsyncIOScheduler
# Daily 8am job:
#   1. Pull data (from DB or Drive)
#   2. Run analysis agent
#   3. Email report via action agent
#   4. Create calendar event for anomalies
# Configurable via /scheduler/jobs API endpoints
```

---

## DEMO SCENARIO (what to show in interviews)

"Every morning at 8 AM, OpsAgent autonomously:
1. Checks GitHub for new issues and categorizes them
2. Pulls last night's data from the database
3. Runs Python analysis and generates a chart
4. Searches the web for relevant industry news
5. Emails a summary report to the team via Gmail
6. Creates a Jira ticket for any critical issues
7. Can answer follow-up questions by voice in real time
8. Remembers context from previous conversations"

---

## RULES FOR THE LLM HELPING WITH THIS PROJECT

1. All LLM calls use Groq free API. Never use OpenAI or Anthropic API keys in application code.
2. Use async/await throughout — FastAPI and LangGraph are both async.
3. Always use python-dotenv + os.getenv() for secrets. Never hardcode API keys.
4. Every agent node must handle exceptions and return error state, never raise uncaught.
5. Use Pydantic models for all inputs/outputs between agents.
6. When writing Dockerfiles, always use python:3.11-slim as base.
7. LangSmith tracing must be enabled — never remove those env vars.
8. RAGAS eval suite runs in ~/eval_venv (separate from main .venv).
9. All file paths are relative to the repo root ~/Desktop/\$\$\$\$/opsagent.
10. When in doubt about which Groq model to use, default to llama-3.3-70b-versatile.
11. Main venv is at ~/Desktop/\$\$\$\$/opsagent/.venv
12. Eval venv is at ~/eval_venv
13. Docker services started with: docker compose -f infra/docker-compose.yml up -d
14. Always source .venv before running python commands.

---

## GROQ USAGE STRATEGY (token efficiency)

| Task                        | Model                      |
|-----------------------------|----------------------------|
| Orchestrator planning       | llama-3.3-70b-versatile    |
| RAG answer synthesis        | llama-3.3-70b-versatile    |
| Router classification       | llama-3.1-8b-instant       |
| Guardrail detection         | llama-3.1-8b-instant       |
| Memory importance scoring   | llama-3.1-8b-instant       |
| Critic scoring              | llama-3.1-8b-instant       |
| Browser action decision     | llama-3.3-70b-versatile    |
| Code generation + execution | llama-3.3-70b-versatile    |
| Final answer synthesis      | llama-3.3-70b-versatile    |

---

## KNOWN ISSUES / TECH DEBT

1. Browser agent asyncio conflict fixed with threading.Thread workaround
2. mxbai-embed-large-v1 (1.3GB) needs swap cleared before first load each session
3. ElevenLabs model must be eleven_flash_v2_5 (eleven_monolingual_v1 deprecated on free tier)
4. RAGAS eval runs in ~/eval_venv due to langchain version conflict
5. Qdrant client version mismatch warning (cosmetic, not functional)
6. Google OAuth token.json auto-refreshes but needs re-auth if expired >7 days
7. voice_query.sh requires arecord (alsa-utils) and ffplay (ffmpeg)

---
END OF CONTEXT FILE
