from __future__ import annotations

import hashlib
import logging

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from ..core.config import CHUNK_OVERLAP, CHUNK_SIZE
from ..models.knowledge import KnowledgeDoc

logger = logging.getLogger(__name__)

EXCEL_CHUNK_HEADER_ROWS = 2


def hash_text(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def make_chunk_meta(
    doc: KnowledgeDoc,
    chunk_index: int,
    char_count: int,
    structure: str,
) -> dict:
    return {
        "source": doc.filename,
        "chunk_index": chunk_index,
        "char_count": char_count,
        "summary": doc.summary,
        "file_type": doc.file_type,
        "structure": structure,
        "user_id": doc.user_id,
    }


def chunk_document(text: str, structure: str) -> list[str]:
    chunker = CHUNKERS.get(structure, chunk_semantic)
    return chunker(text)


def chunk_semantic(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "；", "，", ".", "!", "?", ";", " ", ""],
    )
    return splitter.split_text(text)


def chunk_markdown(text: str) -> list[str]:
    headers_to_split_on = [
        ("#", "H1"),
        ("##", "H2"),
        ("###", "H3"),
        ("####", "H4"),
    ]
    try:
        splitter = MarkdownHeaderTextSplitter(headers_to_split_on, strip_headers=False)
        docs = splitter.split_text(text)
        chunks = []
        for doc in docs:
            header = _format_markdown_header(doc.metadata)
            chunk_text = header + doc.page_content
            if len(chunk_text) > CHUNK_SIZE * 3:
                chunks.extend(chunk_semantic(chunk_text))
            else:
                chunks.append(chunk_text)
        return chunks if chunks else chunk_semantic(text)
    except Exception as exc:
        logger.warning("Markdown 分块失败，回退语义分块: %s", exc)
        return chunk_semantic(text)


def chunk_excel(text: str) -> list[str]:
    chunks = []
    for sheet_block in text.split("## Sheet: "):
        if not sheet_block.strip():
            continue

        lines = [line for line in sheet_block.strip().split("\n") if line.strip()]
        if len(lines) <= EXCEL_CHUNK_HEADER_ROWS:
            chunks.append(sheet_block.strip())
            continue

        sheet_name = lines[0]
        header = "\n".join(lines[1:EXCEL_CHUNK_HEADER_ROWS + 1])
        data_rows = lines[EXCEL_CHUNK_HEADER_ROWS + 1:]
        chunk_size_rows = max(1, (CHUNK_SIZE // max(1, len(header.split("\n")[0]))) * 10)

        for index in range(0, len(data_rows), chunk_size_rows):
            batch = data_rows[index:index + chunk_size_rows]
            chunks.append(f"Sheet: {sheet_name}\n{header}\n" + "\n".join(batch))

    return chunks


def _format_markdown_header(metadata: dict) -> str:
    if not metadata:
        return ""

    parts = [value for value in metadata.values() if value]
    if not parts:
        return ""
    return " > ".join(parts) + "\n"


CHUNKERS = {
    "semantic": chunk_semantic,
    "excel": chunk_excel,
    "markdown": chunk_markdown,
}
