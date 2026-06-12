from __future__ import annotations
import uuid
import structlog
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text, Column, String, Text, DateTime, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from pgvector.sqlalchemy import Vector
from fastembed import TextEmbedding
from rag.config import get_settings

log = structlog.get_logger()

Base = declarative_base()


class Memory(Base):
    __tablename__ = "memories"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    memory_type = Column(String, default="fact")
    importance = Column(Float, default=0.5)
    access_count = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow)
    embedding = Column(Vector(1024))


_engine = None
_session_factory = None
_embedder = None


def get_engine():
    global _engine
    if _engine is None:
        s = get_settings()
        _engine = create_engine(s.database_url)
        with _engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        Base.metadata.create_all(_engine)
        log.info("postgres_connected")
    return _engine


def get_session():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine())
    return _session_factory()


def get_embedder():
    global _embedder
    if _embedder is None:
        s = get_settings()
        _embedder = TextEmbedding(
            model_name=s.embed_model,
            cache_dir="/home/sahil/.cache/fastembed"
        )
    return _embedder


def _compute_decay(created_at: datetime, last_accessed: datetime,
                   importance: float) -> float:
    """High importance memories decay slowly. Context memories decay fast."""
    days_since_created = (datetime.utcnow() - created_at).days
    days_since_accessed = (datetime.utcnow() - last_accessed).days
    decay_rate = 0.01 if importance >= 0.8 else 0.05
    decay = max(0.1, 1.0 - (decay_rate * days_since_accessed))
    return decay


def store_memory(user_id: str, content: str,
                 memory_type: str = "fact", importance: float = 0.5) -> str:
    # Check for near-duplicate before storing
    existing = retrieve_memories(user_id, content, top_k=1, similarity_threshold=0.95)
    if existing:
        log.info("memory_deduplicated", content=content[:50])
        return f"Similar memory already exists: {existing[0][:50]}..."

    embedder = get_embedder()
    embedding = list(embedder.embed([content]))[0].tolist()
    session = get_session()
    try:
        memory = Memory(
            id=str(uuid.uuid4()),
            user_id=user_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            embedding=embedding,
        )
        session.add(memory)
        session.commit()
        log.info("memory_stored", user_id=user_id, type=memory_type,
                 importance=importance)
        return f"Memory stored: {content[:50]}..."
    except Exception as e:
        session.rollback()
        log.error("memory_store_error", error=str(e))
        raise
    finally:
        session.close()


def retrieve_memories(user_id: str, query: str, top_k: int = 5,
                      similarity_threshold: float = 0.0) -> list[str]:
    embedder = get_embedder()
    query_embedding = list(embedder.embed([query]))[0].tolist()
    session = get_session()
    try:
        results = session.execute(
            text("""
                SELECT id, content, memory_type, importance,
                       created_at, last_accessed,
                       1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
                FROM memories
                WHERE user_id = :user_id
                AND 1 - (embedding <=> CAST(:embedding AS vector)) > :threshold
                ORDER BY
                    (1 - (embedding <=> CAST(:embedding AS vector))) *
                    importance DESC
                LIMIT :top_k
            """),
            {
                "embedding": str(query_embedding),
                "user_id": user_id,
                "top_k": top_k,
                "threshold": similarity_threshold,
            }
        ).fetchall()

        # Update access count and last_accessed
        for row in results:
            session.execute(
                text("""UPDATE memories SET
                    access_count = access_count + 1,
                    last_accessed = :now
                    WHERE id = :id"""),
                {"now": datetime.utcnow(), "id": row[0]}
            )
        session.commit()

        # Apply decay scoring
        scored = []
        for row in results:
            memory_id, content, mem_type, importance, created_at, last_accessed, similarity = row
            decay = _compute_decay(created_at, last_accessed, importance)
            final_score = similarity * importance * decay
            scored.append((final_score, content))

        scored.sort(key=lambda x: x[0], reverse=True)
        memories = [content for _, content in scored]
        log.info("memories_retrieved", user_id=user_id, count=len(memories))
        return memories
    except Exception as e:
        log.error("memory_retrieve_error", error=str(e))
        return []
    finally:
        session.close()


def consolidate_memories(user_id: str) -> str:
    """Merge very similar memories to avoid redundancy."""
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage, SystemMessage
    s = get_settings()

    session = get_session()
    try:
        results = session.execute(
            text("SELECT id, content FROM memories WHERE user_id = :user_id AND memory_type = 'fact'"),
            {"user_id": user_id}
        ).fetchall()

        if len(results) < 2:
            return "Not enough memories to consolidate."

        memories_text = "\n".join([f"ID:{r[0][:8]} - {r[1]}" for r in results])
        llm = ChatGroq(model=s.groq_model_fast, api_key=s.groq_api_key, temperature=0)
        response = llm.invoke([
            SystemMessage(content="""Find duplicate or very similar memories and return 
            IDs to delete as JSON array. Return [] if nothing to delete. 
            Return ONLY JSON array of ID prefixes (first 8 chars)."""),
            HumanMessage(content=memories_text),
        ])

        import json
        raw = response.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        to_delete = json.loads(raw)

        deleted = 0
        for id_prefix in to_delete:
            for row in results:
                if row[0].startswith(id_prefix):
                    session.execute(
                        text("DELETE FROM memories WHERE id = :id"),
                        {"id": row[0]}
                    )
                    deleted += 1

        session.commit()
        log.info("memories_consolidated", deleted=deleted)
        return f"Consolidated memories: {deleted} duplicates removed."
    except Exception as e:
        session.rollback()
        log.error("consolidation_error", error=str(e))
        return f"Consolidation failed: {str(e)}"
    finally:
        session.close()


def list_memories(user_id: str) -> list[dict]:
    session = get_session()
    try:
        results = session.execute(
            text("""SELECT id, content, memory_type, importance, 
                   access_count, created_at 
                   FROM memories WHERE user_id = :user_id 
                   ORDER BY importance DESC, created_at DESC"""),
            {"user_id": user_id}
        ).fetchall()
        return [{
            "id": r[0], "content": r[1], "type": r[2],
            "importance": r[3], "access_count": r[4],
            "created_at": str(r[5])
        } for r in results]
    finally:
        session.close()


def delete_memory(memory_id: str) -> str:
    session = get_session()
    try:
        session.execute(text("DELETE FROM memories WHERE id = :id"),
                        {"id": memory_id})
        session.commit()
        return f"Memory {memory_id} deleted."
    finally:
        session.close()

def get_top_memories(user_id: str, top_k: int = 5) -> list[str]:
    """Get most important memories regardless of query."""
    session = get_session()
    try:
        results = session.execute(
            text("""SELECT content FROM memories 
                   WHERE user_id = :user_id 
                   AND memory_type = 'fact'
                   ORDER BY importance DESC, access_count DESC
                   LIMIT :top_k"""),
            {"user_id": user_id, "top_k": top_k}
        ).fetchall()
        return [r[0] for r in results]
    except Exception as e:
        return []
    finally:
        session.close()