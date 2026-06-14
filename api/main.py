import json
import base64
import structlog
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from rag.chain import answer
from rag.ingest import ingest_csv, ingest_pdf, ingest_url
from rag.models import IngestResult, RAGResponse
from rag.store import ensure_collection, get_client
from fastapi import BackgroundTasks
import os
from dotenv import load_dotenv
load_dotenv()

# Set LangSmith vars before any langchain imports
os.environ.setdefault("LANGCHAIN_TRACING_V2", os.getenv("LANGCHAIN_TRACING_V2", "false"))
os.environ.setdefault("LANGCHAIN_API_KEY", os.getenv("LANGCHAIN_API_KEY", ""))
os.environ.setdefault("LANGCHAIN_PROJECT", os.getenv("LANGCHAIN_PROJECT", "opsagent"))
os.environ.setdefault("LANGSMITH_API_KEY", os.getenv("LANGSMITH_API_KEY", ""))
os.environ.setdefault("LANGSMITH_TRACING", os.getenv("LANGSMITH_TRACING", "false"))
os.environ.setdefault("LANGSMITH_PROJECT", os.getenv("LANGSMITH_PROJECT", "opsagent"))

log = structlog.get_logger()

app = FastAPI(title="RAG Pipeline API", version="0.1.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    ensure_collection()
    log.info("rag_api_started")

# @app.on_event("startup")
# async def startup():
#     ensure_collection()
#     # Preload all models at startup to avoid cold-start crashes
#     from rag.store import get_embedder
#     from rag.reranker import get_reranker
#     from voice.stt import get_model
#     import asyncio
#     loop = asyncio.get_event_loop()
#     await loop.run_in_executor(None, get_embedder)
#     await loop.run_in_executor(None, get_reranker)
#     await loop.run_in_executor(None, get_model)
#     log.info("rag_api_started")


@app.get("/health")
def health():
    try:
        get_client().get_collections()
        return {"status": "ok", "qdrant": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Qdrant unavailable: {e}")


@app.get("/collections")
def list_collections():
    client = get_client()
    result = []
    for col in client.get_collections().collections:
        info = client.get_collection(col.name)
        result.append({"name": col.name, "points": info.points_count, "status": info.status})
    return {"collections": result}


def _bg_upsert(chunks, collection: str, label: str):
    """Embed + upsert chunks in a background thread (slow for large docs)."""
    try:
        from rag.store import upsert_chunks
        n = upsert_chunks(chunks, collection=collection)
        log.info("bg_ingest_done", label=label, chunks=n)
    except Exception as e:
        log.error("bg_ingest_error", label=label, error=str(e))


@app.post("/ingest/pdf", response_model=IngestResult)
async def ingest_pdf_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    collection: Optional[str] = Form(None),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only .pdf files accepted")
    content = await file.read()
    try:
        from rag.loaders import load_pdf
        from rag.chunker import chunk_documents
        from rag.store import ensure_collection
        col = ensure_collection(collection)
        pages = load_pdf(content, file.filename)
        chunks = chunk_documents(pages)
        if not chunks:
            return IngestResult(doc_id="unknown", source=file.filename, chunks_upserted=0, status="success")
        doc_id = chunks[0].metadata.doc_id
        background_tasks.add_task(_bg_upsert, chunks, col, file.filename)
        return IngestResult(doc_id=doc_id, source=file.filename, chunks_upserted=len(chunks), status="success")
    except Exception as e:
        log.error("ingest_pdf_error", error=str(e))
        raise HTTPException(500, str(e))


@app.post("/ingest/csv", response_model=IngestResult)
async def ingest_csv_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    text_columns: Optional[str] = Form(None),
    collection: Optional[str] = Form(None),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only .csv files accepted")
    content = await file.read()
    try:
        from rag.loaders import load_csv
        from rag.chunker import chunk_documents
        from rag.store import ensure_collection
        cols_list = [c.strip() for c in text_columns.split(",")] if text_columns else None
        col = ensure_collection(collection)
        rows = load_csv(content, file.filename, text_columns=cols_list)
        chunks = chunk_documents(rows)
        if not chunks:
            return IngestResult(doc_id="unknown", source=file.filename, chunks_upserted=0, status="success")
        doc_id = chunks[0].metadata.doc_id
        background_tasks.add_task(_bg_upsert, chunks, col, file.filename)
        return IngestResult(doc_id=doc_id, source=file.filename, chunks_upserted=len(chunks), status="success")
    except Exception as e:
        log.error("ingest_csv_error", error=str(e))
        raise HTTPException(500, str(e))


class URLIngestRequest(BaseModel):
    url: str
    collection: Optional[str] = None


@app.post("/ingest/url", response_model=IngestResult)
async def ingest_url_endpoint(
    req: URLIngestRequest,
    background_tasks: BackgroundTasks,
):
    try:
        from rag.loaders import load_url
        from rag.chunker import chunk_documents
        from rag.store import ensure_collection
        col = ensure_collection(req.collection)
        pages = await load_url(req.url)
        chunks = chunk_documents(pages)
        if not chunks:
            return IngestResult(doc_id="unknown", source=req.url, chunks_upserted=0, status="success")
        doc_id = chunks[0].metadata.doc_id
        background_tasks.add_task(_bg_upsert, chunks, col, req.url)
        return IngestResult(doc_id=doc_id, source=req.url, chunks_upserted=len(chunks), status="success")
    except Exception as e:
        log.error("ingest_url_error", error=str(e))
        raise HTTPException(500, str(e))


class QueryRequest(BaseModel):
    query: str
    collection: Optional[str] = None
    filters: Optional[dict] = None


@app.post("/query", response_model=RAGResponse)
def query_endpoint(req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(400, "Query cannot be empty")
    return answer(query=req.query, metadata_filter=req.filters, collection=req.collection)


# ── Agent endpoint ─────────────────────────────────────────────────────────────

from agents.orchestrator import run_agent
from fastapi import BackgroundTasks

class AgentRequest(BaseModel):
    task: str
    user_id: str = "default"
    session_id: Optional[str] = None


def _background_memory(task: str, answer: str, user_id: str):
    try:
        from memory.extractor import extract_memories
        from memory.scorer import should_store
        from memory.long_term import store_memory
        extracted = extract_memories(task, answer)
        for fact in extracted[:2]:
            if should_store(fact, threshold=0.6):
                store_memory(user_id=user_id, content=fact,
                           memory_type="fact", importance=0.8)
    except Exception as e:
        log.error("background_memory_error", error=str(e))


@app.post("/agent")
def agent_endpoint(req: AgentRequest, background_tasks: BackgroundTasks):
    try:
        result = run_agent(task=req.task, user_id=req.user_id,
                          session_id=req.session_id)
        if result.get("answer"):
            background_tasks.add_task(
                _background_memory, req.task, result["answer"], req.user_id
            )
        return result
    except Exception as e:
        log.error("agent_endpoint_error", error=str(e))
        raise HTTPException(500, str(e))

# ── Memory endpoints ───────────────────────────────────────────────────────────

from memory.long_term import store_memory, retrieve_memories, list_memories, delete_memory

class MemoryStoreRequest(BaseModel):
    user_id: str
    content: str
    memory_type: str = "fact"

class MemoryRetrieveRequest(BaseModel):
    user_id: str
    query: str
    top_k: int = 5

@app.post("/memory/store")
def memory_store(req: MemoryStoreRequest):
    result = store_memory(req.user_id, req.content, req.memory_type)
    return {"status": "success", "result": result}

@app.post("/memory/retrieve")
def memory_retrieve(req: MemoryRetrieveRequest):
    memories = retrieve_memories(req.user_id, req.query, req.top_k)
    return {"memories": memories}

@app.get("/memory/{user_id}")
def memory_list(user_id: str):
    memories = list_memories(user_id)
    return {"memories": memories}

@app.delete("/memory/{memory_id}")
def memory_delete(memory_id: str):
    result = delete_memory(memory_id)
    return {"status": "success", "result": result}

@app.post("/memory/consolidate/{user_id}")
def memory_consolidate(user_id: str):
    from memory.long_term import consolidate_memories
    result = consolidate_memories(user_id)
    return {"status": "success", "result": result}

@app.get("/memory/summary/{user_id}")
def memory_summary(user_id: str):
    from memory.summarizer import summarize_memories
    summary = summarize_memories(user_id)
    return {"user_id": user_id, "summary": summary}

@app.get("/conversation/{user_id}/history")
def conversation_history(user_id: str, turns: int = 10):
    from memory.conversation import get_recent_history
    history = get_recent_history(user_id, turns=turns)
    return {"user_id": user_id, "history": history}

@app.get("/conversation/{user_id}/session/{session_id}")
def session_history(user_id: str, session_id: str):
    from memory.conversation import get_session_history
    history = get_session_history(user_id, session_id)
    return {"user_id": user_id, "session_id": session_id, "history": history}


# ── Voice WebSocket ────────────────────────────────────────────────────────────

from fastapi import WebSocket
from api.ws import voice_ws_endpoint

@app.websocket("/voice")
async def voice_endpoint(websocket: WebSocket):
    await voice_ws_endpoint(websocket)


# ── Voice REST endpoints ───────────────────────────────────────────────────────

from fastapi import UploadFile, File
from fastapi.responses import Response

@app.post("/voice/transcribe")
async def transcribe_endpoint(file: UploadFile = File(...)):
    from voice.stt import transcribe_audio
    audio_bytes = await file.read()
    transcript = transcribe_audio(audio_bytes)
    return {"transcript": transcript}

@app.post("/voice/speak")
def speak_endpoint(text: str):
    from voice.tts import text_to_speech
    audio_bytes = text_to_speech(text)
    return Response(content=audio_bytes, media_type="audio/mpeg")

@app.post("/voice/ask")
async def voice_ask_endpoint(
    file: UploadFile = File(...),
    user_id: str = "default"
):
    from voice.stt import transcribe_audio
    from voice.tts import text_to_speech
    audio_bytes = await file.read()
    transcript = transcribe_audio(audio_bytes)
    result = run_agent(task=transcript, user_id=user_id)
    answer_text = result.get("answer", "")
    audio_response = text_to_speech(answer_text)
    audio_b64 = base64.b64encode(audio_response).decode("utf-8")
    return {
        "transcript": transcript,
        "answer": answer_text,
        "agent_used": result.get("agent_used"),
        "audio_b64": audio_b64,
    }


# ── Eval endpoint ──────────────────────────────────────────────────────────────

@app.post("/eval/run")
def run_eval_endpoint():
    try:
        from evals.rag_eval import run_eval
        results = run_eval()
        return results
    except Exception as e:
        log.error("eval_error", error=str(e))
        raise HTTPException(500, str(e))

@app.get("/eval/results")
def get_eval_results():
    try:
        with open("evals/results.json") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(404, "No eval results yet. Run POST /eval/run first.")


# ── HITL endpoints ─────────────────────────────────────────────────────────────

@app.post("/agent/approve/{trace_id}")
def approve_endpoint(trace_id: str):
    from agents.action_agent import approve_action
    result = approve_action(trace_id)
    return {"status": "approved", "result": result}

@app.post("/agent/reject/{trace_id}")
def reject_endpoint(trace_id: str):
    from agents.action_agent import reject_action
    result = reject_action(trace_id)
    return {"status": "rejected", "result": result}

@app.get("/agent/pending")
def pending_approvals():
    from agents.action_agent import _pending_approvals
    return {"pending": list(_pending_approvals.keys())}


# ── GitHub HITL endpoints ──────────────────────────────────────────────────────

@app.post("/agent/approve/github/{trace_id}")
def approve_github_endpoint(trace_id: str):
    from agents.github_agent import approve_github_action
    result = approve_github_action(trace_id)
    return {"status": "approved", "result": result}

@app.post("/agent/reject/github/{trace_id}")
def reject_github_endpoint(trace_id: str):
    from agents.github_agent import reject_github_action
    result = reject_github_action(trace_id)
    return {"status": "rejected", "result": result}


# ── Streaming endpoint ─────────────────────────────────────────────────────────

from fastapi.responses import StreamingResponse
from rag.chain import answer_stream

@app.get("/stream")
async def stream_endpoint(task: str, user_id: str = "default"):
    from memory.long_term import retrieve_memories, get_top_memories
    from memory.conversation import store_turn

    # Inject memory context
    semantic = retrieve_memories(user_id, task, top_k=5)
    top = get_top_memories(user_id, top_k=3)
    all_mem = list(dict.fromkeys(semantic + top))
    memory_context = "\n".join(f"- {m}" for m in all_mem[:8])

    store_turn(user_id, "stream", "user", task)

    # def generate():
    #     full_response = ""
    #     # Send memory context as first SSE event
    #     if memory_context:
    #         yield f"data: [CONTEXT]{memory_context}[/CONTEXT]\n\n"

    #     # Stream the answer
    #     for token in answer_stream(task):
    #         full_response += token
    #         yield f"data: {token}\n\n"

    #     # Send done signal
    #     yield "data: [DONE]\n\n"

    #     # Store response in background
    #     store_turn(user_id, "stream", "assistant", full_response)

    def generate():
        full_response = ""
        
        if memory_context:
            yield f"data: [CONTEXT]{memory_context}[/CONTEXT]\n\n"

        # Check if RAG has relevant docs
        from rag.retriever import HybridRetriever
        retriever = HybridRetriever()
        chunks = retriever.retrieve(task)
        
        # RRF scores top out at ~0.033; any result means we have relevant KB content
        if chunks:
            # Use RAG streaming
            for token in answer_stream(task):
                full_response += token
                yield f"data: {token}\n\n"
        else:
            # Use direct LLM streaming with memory context
            from groq import Groq
            from rag.config import get_settings
            s = get_settings()
            client = Groq(api_key=s.groq_api_key)
            
            system = "You are a helpful assistant. Be concise and accurate."
            if memory_context:
                system += f"\n\nWhat you know about the user:\n{memory_context}"
            
            stream = client.chat.completions.create(
                model=s.groq_model_large,
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": task},
                ],
                stream=True,
            )
            for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    full_response += token
                    yield f"data: {token}\n\n"

        yield "data: [DONE]\n\n"
        store_turn(user_id, "stream", "assistant", full_response)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
