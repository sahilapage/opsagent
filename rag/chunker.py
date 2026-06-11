import structlog
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.config import get_settings
from rag.models import Chunk, DocumentMetadata

log = structlog.get_logger()


def chunk_documents(
    pages: list[tuple[str, DocumentMetadata]],
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> list[Chunk]:
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.chunk_size,
        chunk_overlap=chunk_overlap or settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    all_chunks = []
    for text, base_meta in pages:
        if not text.strip():
            continue
        splits = splitter.split_text(text)
        total = len(splits)
        for i, split_text in enumerate(splits):
            meta = base_meta.model_copy(update={"chunk_index": i, "total_chunks": total})
            all_chunks.append(Chunk(text=split_text.strip(), metadata=meta))
    log.info("chunking_done", input_pages=len(pages), output_chunks=len(all_chunks))
    return all_chunks
