from rag.retriever import HybridRetriever
from rag.chain import answer as rag_answer

def search_knowledge_base(query: str, top_k: int = 5) -> str:
    retriever = HybridRetriever()
    results = retriever.retrieve(query)
    if not results:
        return "No relevant results found."
    output = ""
    for i, r in enumerate(results[:top_k], 1):
        source = r.metadata.get("source", "unknown")
        page = r.metadata.get("page", "")
        output += f"[{i}] ({source}, page {page})\n{r.text}\n\n"
    return output

def answer_from_kb(query: str) -> str:
    result = rag_answer(query=query)
    return result.answer
