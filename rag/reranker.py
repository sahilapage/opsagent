import structlog
from sentence_transformers import CrossEncoder
from rag.models import SearchResult

log = structlog.get_logger()

_reranker = None

def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        log.info("reranker_loaded", model="cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker


def rerank(query: str, candidates: list[SearchResult], top_k: int = 5) -> list[SearchResult]:
    if not candidates:
        return []

    reranker = get_reranker()
    pairs = [[query, c.text] for c in candidates]
    scores = reranker.predict(pairs)

    ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
    results = [c for _, c in ranked[:top_k]]

    log.info("reranked", input=len(candidates), output=len(results), query=query)
    return results
