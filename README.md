# OpsAgent

A production-grade autonomous AI agent system built with LangGraph, Groq, and a full React frontend. OpsAgent routes tasks across specialized agents — RAG retrieval, web browsing, code execution, GitHub automation, Gmail/Calendar/Drive integration, and more — with human-in-the-loop approval for high-stakes actions.

---

## What it does

OpsAgent takes a natural language task, decides which agent (or combination of agents) handles it, runs the task, and returns a grounded answer. It maintains long-term memory across sessions, runs a guardrail pass on every input, and holds destructive actions (sending emails, creating GitHub PRs, etc.) for explicit human approval before executing.

**Agents:**

| Agent | What it handles |
|---|---|
| **RAG** | Questions over ingested documents — hybrid dense + BM25 retrieval with cross-encoder reranking |
| **Analysis** | Math, statistics, data reasoning |
| **Browser** | Web search (Serper) and headless scraping (Playwright) |
| **Code** | Generates and executes Python in a sandbox, including matplotlib charts |
| **Action** | Gmail (read/send), Google Calendar (list/create events), Google Drive (list files) |
| **GitHub** | Issues, PRs, commits, branches, code review, auto-fix with PR creation |
| **General** | Fallback LLM for world knowledge and conversation |
| **Planner** | Decomposes multi-step tasks and sequences the above agents |
| **Guardrail** | Blocks prompt injection, jailbreaks, and system attacks before routing |
| **Critic** | Scores answers post-generation and rewrites if quality falls below threshold |

---

## Architecture

```
User request
    ↓
Guardrail check
    ↓
Planner (multi-step?) ──→ Router ──→ Agent
                                        ↓
                                    Critic (score & rewrite)
                                        ↓
                                    Long-term memory store
                                        ↓
                                    Response
```

**Stack:**
- **LLM:** Groq — `llama-3.3-70b-versatile` (reasoning), `llama-3.1-8b-instant` (fast tasks)
- **Orchestration:** LangGraph `StateGraph` with conditional edges
- **Vector DB:** Qdrant with hybrid search — dense embeddings (mxbai-embed-large-v1, 1024d) + BM25 sparse, fused via RRF
- **Reranker:** `cross-encoder/ms-marco-MiniLM-L-6-v2` (local)
- **Long-term memory:** PostgreSQL + pgvector, similarity search across sessions
- **API:** FastAPI + Uvicorn
- **Frontend:** React 19 + Vite
- **Tracing:** LangSmith
- **MCP:** stdio-based Model Context Protocol server exposing 8 tools for external callers (e.g. Claude Desktop)

---

## Project structure

```
opsagent/
├── agents/
│   ├── orchestrator.py      # LangGraph state machine — routing, planner, critic wiring
│   ├── rag_agent.py         # Hybrid retrieval + reranking
│   ├── analysis_agent.py    # LLM reasoning for data/math
│   ├── browser_agent.py     # Serper search + Playwright scrape
│   ├── code_agent.py        # Python sandbox execution
│   ├── action_agent.py      # Gmail, Calendar, Drive + HITL gate
│   ├── github_agent.py      # GitHub API + HITL gate
│   ├── planner_agent.py     # Multi-step task decomposition
│   ├── guardrail_agent.py   # Security filtering
│   ├── critic_agent.py      # Answer quality scoring + rewrite
│   └── state.py             # Shared AgentState TypedDict
├── rag/
│   ├── chain.py             # RAG chain (retrieve → rerank → generate)
│   ├── retriever.py         # HybridRetriever (dense + BM25 + RRF)
│   ├── ingest.py            # PDF, CSV, URL ingestion
│   ├── store.py             # Qdrant client + collection management
│   ├── reranker.py          # Cross-encoder reranker
│   └── config.py            # Settings (Groq, Qdrant, Postgres)
├── memory/
│   ├── long_term.py         # pgvector memory store + retrieval
│   ├── conversation.py      # Per-session turn history
│   ├── extractor.py         # LLM-based fact extraction from conversations
│   ├── scorer.py            # Importance scoring for memory deduplication
│   └── summarizer.py        # Memory summarisation
├── api/
│   ├── main.py              # FastAPI app — all REST endpoints
│   └── ws.py                # WebSocket voice endpoint
├── mcp_servers/
│   ├── server.py            # MCP server — 8 tools over stdio
│   └── client.py            # MCP client (used by external callers)
├── voice/
│   ├── stt.py               # Whisper speech-to-text
│   └── tts.py               # Text-to-speech
├── evals/
│   └── rag_eval.py          # RAGAS evaluation suite
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js           # Axios client + SSE streaming
│   │   └── components/
│   │       ├── Chat.jsx     # Main chat UI with streaming
│   │       ├── Sidebar.jsx
│   │       ├── Ingest.jsx   # Document ingestion UI
│   │       ├── Memory.jsx   # Memory management UI
│   │       ├── Approvals.jsx # HITL approval panel
│   │       └── Settings.jsx
│   └── vite.config.js
└── infra/
    └── docker-compose.yml   # Qdrant + PostgreSQL/pgvector
```

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/sahilapage/opsagent
cd opsagent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Install optional dependencies for full functionality:

```bash
# Browser agent
pip install playwright && python3 -m playwright install chromium

# Voice (Whisper)
pip install openai-whisper

# Google integrations
pip install google-auth google-auth-oauthlib google-api-python-client

# GitHub agent
pip install PyGithub

# MCP server
pip install "mcp[cli]"

# Date parsing for calendar
pip install python-dateutil
```

### 2. Start infrastructure

```bash
docker compose -f infra/docker-compose.yml up -d
```

This starts:
- **Qdrant** on `localhost:6333` — vector store for RAG
- **PostgreSQL/pgvector** on `localhost:5432` — long-term memory

### 3. Configure environment

Copy and fill in your keys:

```bash
cp .env.example .env
```

```env
# LLM
GROQ_API_KEY=your_groq_api_key

# Vector DB
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=opsagent
POSTGRES_USER=opsagent
POSTGRES_PASSWORD=opsagent_secret
DATABASE_URL=postgresql://opsagent:opsagent_secret@localhost:5432/opsagent

# Web search (Browser agent)
SERPER_API_KEY=your_serper_api_key

# GitHub agent
GITHUB_TOKEN=your_github_pat
GITHUB_DEFAULT_REPO=username/repo

# Tracing (optional)
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=opsagent
```

### 4. Google OAuth (Gmail / Calendar / Drive)

Create a project in Google Cloud Console, enable Gmail, Calendar, and Drive APIs, download `credentials.json`, then run:

```bash
python3 auth_google.py
```

This produces `token.json`. The action agent uses it for all Google API calls and auto-refreshes it when it expires.

### 5. Start the backend

```bash
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### 6. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`. In dev mode, `/api/*` requests are proxied to `:8000`.

For production:

```bash
VITE_API_URL=https://your-backend.com npm run build
npm run preview
```

---

## API reference

### Agent

| Method | Path | Description |
|---|---|---|
| `POST` | `/agent` | Run a task — body: `{task, user_id, session_id}` |
| `GET` | `/stream?task=...&user_id=...` | SSE token streaming |
| `GET` | `/agent/pending` | List pending HITL approvals |
| `POST` | `/agent/approve/{trace_id}` | Approve a pending action |
| `POST` | `/agent/reject/{trace_id}` | Reject a pending action |
| `POST` | `/agent/approve/github/{trace_id}` | Approve a pending GitHub action |
| `POST` | `/agent/reject/github/{trace_id}` | Reject a pending GitHub action |

### RAG / Ingestion

| Method | Path | Description |
|---|---|---|
| `POST` | `/ingest/pdf` | Ingest a PDF (`multipart/form-data`) |
| `POST` | `/ingest/csv` | Ingest a CSV |
| `POST` | `/ingest/url` | Ingest a URL — body: `{url}` |
| `POST` | `/query` | Direct RAG query — body: `{query, filters}` |
| `GET` | `/collections` | List Qdrant collections |

### Memory

| Method | Path | Description |
|---|---|---|
| `GET` | `/memory/{user_id}` | List all memories |
| `POST` | `/memory/store` | Manually store a memory |
| `POST` | `/memory/retrieve` | Semantic memory retrieval |
| `DELETE` | `/memory/{memory_id}` | Delete a memory |
| `POST` | `/memory/consolidate/{user_id}` | Deduplicate and merge |
| `GET` | `/memory/summary/{user_id}` | LLM summary of all memories |

### Other

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check (API + Qdrant) |
| `POST` | `/voice/transcribe` | Whisper STT — `multipart/form-data` audio |
| `POST` | `/voice/speak?text=...` | TTS — returns audio/mpeg |
| `WS` | `/voice` | Full-duplex voice WebSocket |

---

## Human-in-the-loop

High-stakes actions pause and wait for approval before executing. The agent returns immediately with a trace ID; the actual action runs only after `POST /agent/approve/{trace_id}`.

**Requires approval:**
- Gmail: send email
- Calendar: create event
- GitHub: create issue, close issue, create branch, create PR, merge PR, auto-fix issue

**Executes immediately:**
- Gmail: read emails
- Calendar: list events
- Drive: list files
- GitHub: all read operations (list, get, search, review, suggest fix, workflow runs)

Approvals expire after 5 minutes. The frontend Approvals tab polls `/agent/pending` every 15 seconds.

---

## MCP server

OpsAgent exposes a Model Context Protocol server for use with external clients such as Claude Desktop:

```bash
python3 mcp_servers/server.py
```

**Tools:**

| Tool | Description |
|---|---|
| `search_kb` | Search the Qdrant knowledge base |
| `run_analysis` | RAG query with grounded answer |
| `send_email` | Send via Gmail |
| `read_emails` | Read Gmail inbox |
| `create_calendar_event` | Create a Google Calendar event |
| `list_calendar_events` | List upcoming events |
| `list_drive_files` | List Google Drive files |
| `get_memory` | Retrieve stored memories for a user |

To use with Claude Desktop, add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "opsagent": {
      "command": "python3",
      "args": ["/absolute/path/to/opsagent/mcp_servers/server.py"]
    }
  }
}
```

---

## Ingesting documents

Via the frontend Knowledge Base tab, or directly:

```bash
# PDF
curl -X POST http://localhost:8000/ingest/pdf -F "file=@document.pdf"

# URL
curl -X POST http://localhost:8000/ingest/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/docs"}'
```

Documents are chunked, embedded (dense 1024d + BM25 sparse), and stored in Qdrant. The RAG agent retrieves with hybrid search, RRF fusion, and cross-encoder reranking.

---

## Tracing

Set `LANGSMITH_TRACING=true` in `.env` to enable LangSmith tracing. Every agent node is decorated with `@traceable`, giving a full per-request trace tree in the LangSmith dashboard.

---

## Deployment (Railway + Vercel)

### Backend on Railway

1. **Create a Railway project** at [railway.app](https://railway.app) and connect your GitHub repo.

2. **Add PostgreSQL plugin** — Railway dashboard → New → Database → PostgreSQL. Copy the `DATABASE_URL` it generates.

3. **Set up Qdrant Cloud** (free tier at [cloud.qdrant.io](https://cloud.qdrant.io)):
   - Create a cluster, copy the cluster URL and API key.

4. **Set environment variables** in Railway service settings:

   ```
   GROQ_API_KEY=...
   QDRANT_URL=https://xxxx.aws.cloud.qdrant.io:6333
   QDRANT_API_KEY=...
   DATABASE_URL=<railway postgres url>
   GITHUB_TOKEN=...
   GITHUB_DEFAULT_REPO=username/repo
   SERPER_API_KEY=...
   LANGCHAIN_API_KEY=...
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_PROJECT=opsagent
   APP_ENV=production
   ```

   For Google integrations, run `python3 auth_google.py` locally to generate `token.json`, then paste its contents as:
   ```
   GOOGLE_TOKEN_JSON={"token":"...","refresh_token":"...","client_id":"...","client_secret":"...","scopes":[...]}
   ```

5. Railway detects `Dockerfile` and `railway.toml` automatically. Deploy triggers on push to main.

6. Note the Railway service URL (e.g. `https://opsagent-production.up.railway.app`).

### Frontend on Vercel

1. Import the repo at [vercel.com/new](https://vercel.com/new), set root directory to `frontend/`.

2. Add environment variable:
   ```
   VITE_API_URL=https://opsagent-production.up.railway.app
   ```

3. Deploy. Vercel auto-detects Vite. `vercel.json` handles SPA routing.

The frontend calls `VITE_API_URL` for all API requests. CORS is open by default — restrict `allow_origins` in `api/main.py` before production use.
