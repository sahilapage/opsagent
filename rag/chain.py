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
        page = meta.get("page", "")
        parts.append(f"[Source {i}] ({source}, page {page})\n{c.text}")
    return "\n\n".join(parts)


def answer(
    query: str,
    metadata_filter: dict | None = None,
    collection: str | None = None,
) -> RAGResponse:
    s = get_settings()
    retriever = HybridRetriever(collection=collection)
    chunks = retriever.retrieve(query, metadata_filter=metadata_filter)
    context = build_context(chunks)

    system_prompt = """You are a precise question-answering assistant.
Answer ONLY using the provided context chunks below.
If the answer is not explicitly in the context, say "This information is not in the provided documents."
Always cite sources using [Source N] inline.
Never add information from outside the provided context.
End with a Sources section listing which sources you used."""

    user_prompt = f"""Context:
{context}

Question: {query}"""

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
