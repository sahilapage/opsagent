from __future__ import annotations
import concurrent.futures
import hashlib
import re
import structlog
from groq import Groq

from rag.config import get_settings
from rag.models import SearchResult
from rag.store import hybrid_search

log = structlog.get_logger()


def _expand_queries(query: str) -> list[str]:
    """Generate 3 alternative phrasings for better recall (multi-query retrieval)."""
    try:
        s = get_settings()
        client = Groq(api_key=s.groq_api_key)
        resp = client.chat.completions.create(
            model=s.groq_model_fast,
            max_tokens=120,
            temperature=0.3,
            messages=[{"role": "user", "content": (
                "Generate 2 alternative search queries for the question below.\n"
                "Each must approach it from a different angle or use different vocabulary.\n"
                "Output ONLY the queries, one per line, no numbering or explanation.\n\n"
                f"Question: {query}"
            )}],
        )
        lines = [l.strip() for l in resp.choices[0].message.content.strip().split('\n')
                 if l.strip() and l.strip().lower() != query.lower()]
        return [query] + lines[:2]
    except Exception as e:
        log.warning("expand_queries_failed", error=str(e))
        return [query]


def _hyde_document(query: str) -> str:
    """Generate a hypothetical passage that answers the query (HyDE technique).

    Embedding a hypothetical answer bridges the vocabulary gap between the
    query and the actual document text — it embeds "as a document", not "as a question".
    """
    try:
        s = get_settings()
        client = Groq(api_key=s.groq_api_key)
        resp = client.chat.completions.create(
            model=s.groq_model_fast,
            max_tokens=180,
            temperature=0.1,
            messages=[{"role": "user", "content": (
                "Write a short passage (3-5 sentences) that would directly and specifically "
                "answer the following question. Write it as if it were extracted verbatim "
                "from a technical document or report.\n\n"
                f"Question: {query}\nPassage:"
            )}],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        log.warning("hyde_failed", error=str(e))
        return query


def _multi_rrf(result_lists: list[list[SearchResult]], k: int = 60) -> list[SearchResult]:
    """RRF across multiple result lists — deduplicates by text hash."""
    scores: dict[str, float] = {}
    store: dict[str, SearchResult] = {}
    for results in result_lists:
        for rank, hit in enumerate(results):
            pid = hashlib.md5(hit.text.encode()).hexdigest()
            scores[pid] = scores.get(pid, 0.0) + 1.0 / (k + rank + 1)
            if pid not in store:
                store[pid] = hit
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [
        SearchResult(text=store[pid].text, score=score, metadata=store[pid].metadata)
        for pid, score in ranked
    ]


def _deduplicate(results: list[SearchResult], threshold: float = 0.82) -> list[SearchResult]:
    """Remove near-duplicate chunks using Jaccard similarity on word sets."""
    kept: list[SearchResult] = []
    kept_words: list[set] = []
    for r in results:
        words = set(r.text.lower().split())
        if not any(
            len(words & w) / max(len(words | w), 1) > threshold
            for w in kept_words
        ):
            kept.append(r)
            kept_words.append(words)
    return kept


def _llm_rerank(query: str, candidates: list[SearchResult], top_k: int) -> list[SearchResult]:
    """Ask the fast LLM to re-score candidates by relevance to the query.

    RRF gives good recall but the final ordering can still be noisy. A dedicated
    reranking pass with an LLM dramatically improves precision.
    """
    if len(candidates) <= top_k:
        return candidates
    try:
        s = get_settings()
        client = Groq(api_key=s.groq_api_key)
        items = []
        for i, c in enumerate(candidates):
            src = c.metadata.get("source", "?")
            snippet = c.text[:280].replace("\n", " ")
            items.append(f"[{i + 1}] Source: {src}\n{snippet}")

        prompt = (
            f"Question: {query}\n\n"
            f"From the passages below, select the {top_k} that best answer the question. "
            f"Output ONLY a comma-separated list of their numbers, most relevant first. "
            f"Example: 3,1,7\n\n"
            + "\n\n".join(items)
            + f"\n\nBest {top_k} passage numbers:"
        )
        resp = client.chat.completions.create(
            model=s.groq_model_fast,
            max_tokens=40,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.choices[0].message.content.strip()
        indices = [
            int(x.strip()) - 1
            for x in re.split(r"[,\s]+", raw)
            if x.strip().isdigit()
        ]
        valid = list(dict.fromkeys(i for i in indices if 0 <= i < len(candidates)))
        reranked = [candidates[i] for i in valid[:top_k]]
        # backfill to top_k if LLM returned fewer
        seen = set(valid[:top_k])
        for i, c in enumerate(candidates):
            if len(reranked) >= top_k:
                break
            if i not in seen:
                reranked.append(c)
        log.info("llm_rerank_done", input=len(candidates), output=len(reranked))
        return reranked
    except Exception as e:
        log.warning("llm_rerank_failed", error=str(e))
        return candidates[:top_k]


class HybridRetriever:
    def __init__(self, collection: str | None = None):
        s = get_settings()
        self.collection = collection
        self.top_k = s.retrieval_top_k
        self.fetch_k = s.retrieval_fetch_k

    def retrieve(
        self,
        query: str,
        metadata_filter: dict | None = None,
        fast: bool = False,
    ) -> list[SearchResult]:
        """Full advanced retrieval pipeline.

        fast=True skips expansion/HyDE/reranking — used for KB probes
        where we only need a quick relevance check, not precise answers.
        """
        if fast:
            results = hybrid_search(
                query=query,
                top_k=self.fetch_k,
                collection=self.collection,
                metadata_filter=metadata_filter,
            )
            return _deduplicate(results)[:self.top_k]

        # ── 1. Parallel: query expansion + HyDE (both Groq network calls) ──────
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            f_expand = pool.submit(_expand_queries, query)
            f_hyde = pool.submit(_hyde_document, query)
        queries = f_expand.result()       # [original, alt1, alt2, alt3]
        hyde_text = f_hyde.result()       # hypothetical passage

        # ── 2. Sequential searches (fastembed is not thread-safe) ───────────────
        all_results: list[list[SearchResult]] = []
        for q in queries + [hyde_text]:
            try:
                r = hybrid_search(
                    query=q,
                    top_k=self.fetch_k,
                    collection=self.collection,
                    metadata_filter=metadata_filter,
                )
                all_results.append(r)
            except Exception as e:
                log.warning("search_failed", q=q[:40], error=str(e))

        # ── 3. Multi-list RRF merge ─────────────────────────────────────────────
        merged = _multi_rrf(all_results)

        # ── 4. Remove near-duplicate chunks ────────────────────────────────────
        deduped = _deduplicate(merged)

        # ── 5. LLM rerank top-25 candidates → top_k ────────────────────────────
        top = _llm_rerank(query, deduped[:25], self.top_k)

        log.info(
            "retrieve_done",
            query=query[:60],
            alt_queries=len(queries) - 1,
            hyde_chars=len(hyde_text),
            candidates=len(deduped),
            returned=len(top),
        )
        return top
