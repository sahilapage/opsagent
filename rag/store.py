from __future__ import annotations
import hashlib
import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, SparseVectorParams, SparseIndexParams,
    PointStruct, SparseVector, SearchRequest, NamedVector,
    NamedSparseVector, Filter, FieldCondition, MatchValue
)
from fastembed import TextEmbedding
from rank_bm25 import BM25Okapi
from rag.config import get_settings
from rag.models import SearchResult, Chunk

log = structlog.get_logger()

_client: QdrantClient | None = None
_embedder: TextEmbedding | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        s = get_settings()
        if s.qdrant_url:
            _client = QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key or None)
            log.info("qdrant_connected", url=s.qdrant_url)
        else:
            _client = QdrantClient(host=s.qdrant_host, port=s.qdrant_port)
            log.info("qdrant_connected", host=s.qdrant_host, port=s.qdrant_port)
    return _client


def get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        s = get_settings()
        kwargs: dict = {"model_name": s.embed_model}
        if s.fastembed_cache_dir:
            kwargs["cache_dir"] = s.fastembed_cache_dir
        _embedder = TextEmbedding(**kwargs)
        log.info("embed_model_loaded", model=s.embed_model)
    return _embedder


def ensure_collection(collection: str | None = None) -> str:
    s = get_settings()
    col = collection or s.qdrant_collection
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]
    if col not in existing:
        client.create_collection(
            collection_name=col,
            vectors_config={"dense": VectorParams(size=s.embed_dim, distance=Distance.COSINE)},
            sparse_vectors_config={"bm25": SparseVectorParams(index=SparseIndexParams())},
        )
        log.info("collection_created", collection=col)
    return col


# def _bm25_sparse_vector(text: str) -> SparseVector:
#     tokens = text.lower().split()
#     bm25 = BM25Okapi([tokens])
#     scores = bm25.get_scores(tokens)
#     indices, values = [], []
#     for token, score in zip(tokens, scores):
#         if score > 0:
#             idx = int(hashlib.md5(token.encode()).hexdigest()[:8], 16) % 1_000_000
#             indices.append(idx)
#             values.append(float(score))
#     return SparseVector(indices=indices, values=values)

def _bm25_sparse_vector(text: str) -> SparseVector:
    tokens = text.lower().split()
    if not tokens:
        return SparseVector(indices=[], values=[])
    
    # Count term frequencies
    tf: dict[int, float] = {}
    for token in tokens:
        idx = int(hashlib.md5(token.encode()).hexdigest()[:8], 16) % 1_000_000
        tf[idx] = tf.get(idx, 0) + 1
    
    # Normalize by document length
    max_tf = max(tf.values())
    indices = list(tf.keys())
    values = [v / max_tf for v in tf.values()]
    
    return SparseVector(indices=indices, values=values)


def upsert_chunks(chunks: list[Chunk], collection: str | None = None) -> int:
    s = get_settings()
    col = collection or s.qdrant_collection
    client = get_client()
    embedder = get_embedder()

    texts = [c.text for c in chunks]
    dense_vecs = list(embedder.embed(texts))

    points = []
    for chunk, dvec in zip(chunks, dense_vecs):
        sparse = _bm25_sparse_vector(chunk.text)
        points.append(PointStruct(
            # id=abs(hash(chunk.metadata.doc_id + str(chunk.metadata.chunk_index))) % (2**63),
            id=abs(hash(chunk.metadata.doc_id + str(chunk.metadata.page) + str(chunk.metadata.chunk_index))) % (2**63),
            vector={"dense": dvec.tolist(), "bm25": sparse},
            payload={"text": chunk.text, **chunk.metadata.model_dump()},
        ))

    batch_size = 100
    for i in range(0, len(points), batch_size):
        client.upsert(collection_name=col, points=points[i:i+batch_size])
    log.info("upserted", collection=col, count=len(points))
    return len(points)


def hybrid_search(query: str, top_k: int = 20, collection: str | None = None,
                  metadata_filter: dict | None = None) -> list[SearchResult]:
    s = get_settings()
    col = collection or s.qdrant_collection
    client = get_client()
    embedder = get_embedder()

    dense_vec = list(embedder.embed([query]))[0].tolist()
    sparse_vec = _bm25_sparse_vector(query)

    qdrant_filter = None
    if metadata_filter:
        conditions = [FieldCondition(key=k, match=MatchValue(value=v))
                      for k, v in metadata_filter.items()]
        qdrant_filter = Filter(must=conditions)

    dense_results = client.search(
        collection_name=col,
        query_vector=NamedVector(name="dense", vector=dense_vec),
        limit=top_k,
        query_filter=qdrant_filter,
        with_payload=True,
    )

    result_lists = [dense_results]
    if sparse_vec.indices:
        sparse_results = client.search(
            collection_name=col,
            query_vector=NamedSparseVector(name="bm25", vector=sparse_vec),
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        )
        result_lists.append(sparse_results)

    fused = _rrf(result_lists)
    log.info("hybrid_search", query=query, results=len(fused))
    return fused


def _rrf(result_lists, k: int = 60) -> list[SearchResult]:
    scores: dict[str, float] = {}
    payloads: dict[str, dict] = {}

    for results in result_lists:
        for rank, hit in enumerate(results):
            pid = str(hit.id)
            scores[pid] = scores.get(pid, 0) + 1 / (k + rank + 1)
            payloads[pid] = hit.payload

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    out = []
    for pid, score in ranked:
        p = payloads[pid]
        from rag.models import DocumentMetadata
        out.append(SearchResult(
            text=p.get("text", ""),
            score=score,
            metadata=p,
        ))
    return out
