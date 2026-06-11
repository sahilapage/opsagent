import structlog

from rag.chunker import chunk_documents
from rag.loaders import load_csv, load_pdf, load_url
from rag.models import IngestResult
from rag.store import ensure_collection, upsert_chunks

log = structlog.get_logger()


def ingest_pdf(file_bytes: bytes, filename: str, collection: str = None) -> IngestResult:
    col = ensure_collection(collection)
    try:
        pages = load_pdf(file_bytes, filename)
        chunks = chunk_documents(pages)
        n = upsert_chunks(chunks, collection=col)
        doc_id = chunks[0].metadata.doc_id if chunks else "unknown"
        return IngestResult(doc_id=doc_id, source=filename, chunks_upserted=n, status="success")
    except Exception as e:
        log.error("ingest_pdf_error", filename=filename, error=str(e))
        return IngestResult(doc_id="error", source=filename, chunks_upserted=0, status="error", error=str(e))


def ingest_csv(file_bytes: bytes, filename: str, text_columns: list = None, collection: str = None) -> IngestResult:
    col = ensure_collection(collection)
    try:
        rows = load_csv(file_bytes, filename, text_columns=text_columns)
        chunks = chunk_documents(rows)
        n = upsert_chunks(chunks, collection=col)
        doc_id = chunks[0].metadata.doc_id if chunks else "unknown"
        return IngestResult(doc_id=doc_id, source=filename, chunks_upserted=n, status="success")
    except Exception as e:
        log.error("ingest_csv_error", filename=filename, error=str(e))
        return IngestResult(doc_id="error", source=filename, chunks_upserted=0, status="error", error=str(e))


async def ingest_url(url: str, collection: str = None) -> IngestResult:
    col = ensure_collection(collection)
    try:
        pages = await load_url(url)
        chunks = chunk_documents(pages)
        n = upsert_chunks(chunks, collection=col)
        doc_id = chunks[0].metadata.doc_id if chunks else "unknown"
        return IngestResult(doc_id=doc_id, source=url, chunks_upserted=n, status="success")
    except Exception as e:
        log.error("ingest_url_error", url=url, error=str(e))
        return IngestResult(doc_id="error", source=url, chunks_upserted=0, status="error", error=str(e))
