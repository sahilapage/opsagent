from __future__ import annotations
import uuid
import structlog
from datetime import datetime
from sqlalchemy import create_engine, text, Column, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from rag.config import get_settings

log = structlog.get_logger()

Base = declarative_base()


class ConversationTurn(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    agent_used = Column(String, default="unknown")
    created_at = Column(DateTime, default=datetime.utcnow)


_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        s = get_settings()
        _engine = create_engine(s.database_url)
        Base.metadata.create_all(_engine)
        log.info("conversations_table_ready")
    return _engine


def get_session():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine())
    return _session_factory()


def store_turn(user_id: str, session_id: str, role: str,
               content: str, agent_used: str = "unknown") -> None:
    session = get_session()
    try:
        turn = ConversationTurn(
            id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            agent_used=agent_used,
        )
        session.add(turn)
        session.commit()
        log.info("turn_stored", user_id=user_id, role=role)
    except Exception as e:
        session.rollback()
        log.error("turn_store_error", error=str(e))
    finally:
        session.close()


def get_recent_history(user_id: str, turns: int = 10) -> list[dict]:
    """Get last N conversation turns across all sessions."""
    session = get_session()
    try:
        results = session.execute(
            text("""
                SELECT role, content, agent_used, session_id, created_at
                FROM conversations
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :turns
            """),
            {"user_id": user_id, "turns": turns}
        ).fetchall()
        # Reverse to get chronological order
        results = list(reversed(results))
        return [{
            "role": r[0],
            "content": r[1],
            "agent_used": r[2],
            "session_id": r[3],
            "created_at": str(r[4]),
        } for r in results]
    finally:
        session.close()


def get_session_history(user_id: str, session_id: str) -> list[dict]:
    """Get all turns from a specific session."""
    session = get_session()
    try:
        results = session.execute(
            text("""
                SELECT role, content, agent_used, created_at
                FROM conversations
                WHERE user_id = :user_id AND session_id = :session_id
                ORDER BY created_at ASC
            """),
            {"user_id": user_id, "session_id": session_id}
        ).fetchall()
        return [{
            "role": r[0],
            "content": r[1],
            "agent_used": r[2],
            "created_at": str(r[3]),
        } for r in results]
    finally:
        session.close()


def format_history_for_context(history: list[dict]) -> str:
    """Format conversation history for injection into LLM context."""
    if not history:
        return ""
    lines = []
    for turn in history[-6:]:  # last 6 turns = 3 exchanges
        role = "User" if turn["role"] == "user" else "Assistant"
        lines.append(f"{role}: {turn['content'][:300]}")
    return "\n".join(lines)
