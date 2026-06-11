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
        candidates = hybrid_search(
            query=query,
            top_k=self.fetch_k,
            collection=self.collection,
            metadata_filter=metadata_filter,
        )
        results = rerank(query, candidates, top_k=self.top_k)
        log.info("retrieve_done", query=query, candidates=len(candidates), returned=len(results))
        return results
