from rag.config import get_settings
from rag.models import SearchResult
from rag.store import hybrid_search
from rag.reranker import rerank
import structlog

log = structlog.get_logger()


class HybridRetriever:
    def __init__(self, collection: str | None = None):
        s = get_settings()
        self.collection = collection
        self.top_k = s.retrieval_top_k
        self.fetch_k = s.retrieval_fetch_k

    def retrieve(self, query: str, metadata_filter: dict | None = None) -> list[SearchResult]:
        # Fetch more candidates than needed, RRF fusion already ranks well
        results = hybrid_search(
            query=query,
            top_k=self.fetch_k,
            collection=self.collection,
            metadata_filter=metadata_filter,
        )
        # Cross-encoder reranker (ms-marco) degrades results for document-style
        # queries because it's tuned for web-search pairs; trust RRF instead.
        top = results[:self.top_k]
        log.info("retrieve_done", query=query, candidates=len(results), returned=len(top))
        return top
