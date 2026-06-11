import io
import uuid
from typing import Optional

import httpx
import pandas as pd
import structlog
from bs4 import BeautifulSoup
from pypdf import PdfReader

from rag.models import DocumentMetadata

log = structlog.get_logger()


def load_pdf(file_bytes: bytes, filename: str) -> list[tuple[str, DocumentMetadata]]:
    reader = PdfReader(io.BytesIO(file_bytes))
    doc_id = str(uuid.uuid4())
    results = []
    for page_num, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        meta = DocumentMetadata(
            doc_id=doc_id, source=filename, doc_type="pdf",
            title=filename.replace(".pdf", ""), page=page_num + 1,
        )
        results.append((text, meta))
    log.info("pdf_loaded", filename=filename, pages=len(results))
    return results


def load_csv(
    file_bytes: bytes,
    filename: str,
    text_columns: Optional[list[str]] = None,
) -> list[tuple[str, DocumentMetadata]]:
    df = pd.read_csv(io.BytesIO(file_bytes))
    doc_id = str(uuid.uuid4())
    results = []
    for idx, row in df.iterrows():
        if text_columns:
            cols = [c for c in text_columns if c in df.columns]
            text = " | ".join(str(row[c]) for c in cols if pd.notna(row[c]))
        else:
            text = row.to_json()
        text = text.strip()
        if not text:
            continue
        meta = DocumentMetadata(doc_id=doc_id, source=filename, doc_type="csv", row=int(idx))
        results.append((text, meta))
    log.info("csv_loaded", filename=filename, rows=len(results))
    return results


async def load_url(url: str) -> list[tuple[str, DocumentMetadata]]:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "RAG-Pipeline/1.0"})
        resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    title = soup.title.string if soup.title else url
    doc_id = str(uuid.uuid4())
    meta = DocumentMetadata(doc_id=doc_id, source=url, doc_type="url", title=title, url=url)
    log.info("url_loaded", url=url, chars=len(text))
    return [(text, meta)]
