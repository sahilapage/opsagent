from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import uuid


class DocumentMetadata(BaseModel):
    doc_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str
    doc_type: Literal["pdf", "csv", "url", "text"]
    title: Optional[str] = None
    page: Optional[int] = None
    row: Optional[int] = None
    url: Optional[str] = None
    ingested_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    chunk_index: int = 0
    total_chunks: int = 1


class Chunk(BaseModel):
    text: str
    metadata: DocumentMetadata


class IngestResult(BaseModel):
    doc_id: str
    source: str
    chunks_upserted: int
    status: Literal["success", "error"]
    error: Optional[str] = None


class SearchResult(BaseModel):
    text: str
    score: float
    metadata: dict


class RAGResponse(BaseModel):
    answer: str
    sources: list[SearchResult]
    query: str
