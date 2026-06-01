from __future__ import annotations

import logging
import os
import uuid

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import UPLOAD_DIR
from ..models.knowledge import DocChunk, KnowledgeDoc
from .file_parser import ParseResult, parse_file
from .knowledge_chunking import chunk_document, hash_text, make_chunk_meta
from .knowledge_indexing import embed_and_finalize, rebuild_sparse_index
from .knowledge_llm import parse_with_multimodal, summarize_document
from .vector_store import delete_by_doc_id

logger = logging.getLogger(__name__)


async def save_upload(file_bytes: bytes, filename: str) -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as file:
        file.write(file_bytes)
    return file_path


async def process_document(db: AsyncSession, doc: KnowledgeDoc) -> None:
    try:
        doc.status = "parsing"
        await db.commit()

        parsed = await _parse_document(doc)
        if not parsed.text.strip():
            raise ValueError("文件内容为空或无法解析")

        doc.char_count = len(parsed.text)
        doc.summary = await summarize_document(parsed.text, doc.filename)
        doc.status = "chunking"
        await db.commit()

        chunks = await _create_chunks(db, doc, parsed)
        if not chunks:
            raise ValueError("所有分块均已存在，未产生新的可索引内容")

        doc.chunk_count = len(chunks)
        logger.info("文档 %s: %d chunks 入库", doc.filename, len(chunks))

        if doc.inspect:
            doc.status = "inspecting"
            await db.commit()
            logger.info("文档 %s 进入审查模式", doc.filename)
            return

        await embed_and_finalize(db, doc, chunks)
    except Exception as exc:
        logger.exception("文档处理失败 %s: %s", doc.filename, exc)
        doc.status = "failed"
        doc.error_msg = str(exc)
        await db.commit()


async def finalize_document(db: AsyncSession, doc: KnowledgeDoc) -> None:
    if doc.status != "inspecting":
        raise ValueError(f"文档状态为 '{doc.status}'，无法继续，需要 'inspecting' 状态")
    await embed_and_finalize(db, doc)


async def delete_document(db: AsyncSession, user_id: str, doc_id: str) -> bool:
    doc = (await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id, KnowledgeDoc.user_id == user_id)
    )).scalar_one_or_none()
    if not doc:
        return False

    delete_by_doc_id(doc_id)
    await db.execute(sa_delete(DocChunk).where(DocChunk.doc_id == doc_id))
    _delete_uploaded_file(doc.file_path)

    await db.delete(doc)
    await db.commit()
    await rebuild_sparse_index(db)
    return True


async def _parse_document(doc: KnowledgeDoc) -> ParseResult:
    parsed = parse_file(doc.file_path, doc.file_type)
    if parsed.needs_multimodal:
        parsed.text = await parse_with_multimodal(doc.file_path, doc.file_type, doc.filename)
        parsed.structure = "semantic"
    return parsed


async def _create_chunks(
    db: AsyncSession,
    doc: KnowledgeDoc,
    parsed: ParseResult,
) -> list[DocChunk]:
    raw_chunks = chunk_document(parsed.text, parsed.structure)
    logger.info(
        "文档 %s (type=%s structure=%s): %d chunks",
        doc.filename,
        doc.file_type,
        parsed.structure,
        len(raw_chunks),
    )

    new_chunks = []
    skipped = 0
    for index, chunk_text in enumerate(raw_chunks):
        if not chunk_text.strip():
            continue

        content_hash = hash_text(chunk_text)
        existing = (await db.execute(
            select(DocChunk.id).where(DocChunk.content_hash == content_hash)
        )).scalar_one_or_none()
        if existing:
            skipped += 1
            continue

        chunk = DocChunk(
            doc_id=doc.id,
            chunk_index=index,
            content=chunk_text,
            content_hash=content_hash,
            char_count=len(chunk_text),
            chunk_metadata=make_chunk_meta(doc, index, len(chunk_text), parsed.structure),
        )
        db.add(chunk)
        new_chunks.append(chunk)

    await db.commit()
    if skipped:
        logger.info("文档 %s 去重跳过 %d 个 chunks", doc.filename, skipped)
    return new_chunks


def _delete_uploaded_file(file_path: str | None) -> None:
    if not file_path or not os.path.exists(file_path):
        return

    try:
        os.remove(file_path)
    except OSError:
        pass
