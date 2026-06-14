from __future__ import annotations
import structlog
from groq import Groq
from rag.config import get_settings
from rag.models import RAGResponse, SearchResult
from rag.retriever import HybridRetriever

log = structlog.get_logger()

_client: Groq | None = None


def get_client() -> Groq:
    global _client
    if _client is None:
        s = get_settings()
        _client = Groq(api_key=s.groq_api_key)
    return _client


def build_context(chunks: list[SearchResult]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        meta = c.metadata
        source = meta.get("source", "unknown")
        page = meta.get("page")
        doc_type = meta.get("doc_type", "")
        header = f"[Source {i}] {source}"
        if page:
            header += f" · page {page}"
        if doc_type:
            header += f" [{doc_type.upper()}]"
        # Trim very long chunks to keep context window efficient
        text = c.text if len(c.text) <= 700 else c.text[:700] + "…"
        parts.append(f"{header}\n{text}")
    return "\n\n---\n\n".join(parts)


def answer(
    query: str,
    metadata_filter: dict | None = None,
    collection: str | None = None,
) -> RAGResponse:
    s = get_settings()
    retriever = HybridRetriever(collection=collection)
    chunks = retriever.retrieve(query, metadata_filter=metadata_filter)
    context = build_context(chunks)

    system_prompt = (
        "You are a precise question-answering assistant with access to a knowledge base.\n\n"
        "Rules:\n"
        "- Answer using ONLY the provided context chunks.\n"
        "- Cite sources inline as [Source N] whenever you use information from them.\n"
        "- If multiple sources agree, synthesize them into one clear answer.\n"
        "- If sources conflict, mention both and note the discrepancy.\n"
        "- If the answer is not in the context, say exactly: "
        "'This information is not in the provided documents.'\n"
        "- Be concise and direct. Do not repeat the question."
    )
    user_prompt = f"Context:\n{context}\n\nQuestion: {query}"

    client = get_client()
    message = client.chat.completions.create(
        model=s.groq_model_large,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    answer_text = message.choices[0].message.content
    log.info("rag_answer_generated", query=query, sources=len(chunks))

    return RAGResponse(answer=answer_text, sources=chunks, query=query)

from groq import Groq
from typing import Generator

def answer_stream(
    query: str,
    metadata_filter: dict | None = None,
    collection: str | None = None,
) -> Generator[str, None, None]:
    """Stream RAG answer token by token."""
    s = get_settings()
    retriever = HybridRetriever(collection=collection)
    chunks = retriever.retrieve(query, metadata_filter=metadata_filter)
    context = build_context(chunks)

    system_prompt = (
        "You are a precise question-answering assistant with access to a knowledge base.\n\n"
        "Rules:\n"
        "- Answer using ONLY the provided context chunks.\n"
        "- Cite sources inline as [Source N] whenever you use information from them.\n"
        "- If multiple sources agree, synthesize them into one clear answer.\n"
        "- If sources conflict, mention both and note the discrepancy.\n"
        "- If the answer is not in the context, say exactly: "
        "'This information is not in the provided documents.'\n"
        "- Be concise and direct. Do not repeat the question."
    )
    user_prompt = f"Context:\n{context}\n\nQuestion: {query}"

    client = get_client()
    stream = client.chat.completions.create(
        model=s.groq_model_large,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        stream=True,
    )

    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token