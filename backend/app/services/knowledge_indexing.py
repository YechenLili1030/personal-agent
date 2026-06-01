from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.knowledge import DocChunk, KnowledgeDoc
from .bm25_store import rebuild_bm25_index
from .embedding import embed_texts
from .vector_store import add_chunks

logger = logging.getLogger(__name__)

BATCH_SIZE = 10


async def embed_and_finalize(
    db: AsyncSession,
    doc: KnowledgeDoc,
    chunks: list[DocChunk] | None = None,
) -> None:
    doc.status = "embedding"
    await db.commit()

    chunks = chunks or await _load_doc_chunks(db, doc.id)
    if not chunks:
        raise ValueError("没有找到要嵌入的分块")

    for batch_start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[batch_start:batch_start + BATCH_SIZE]
        texts = [chunk.content for chunk in batch]
        embeddings = await embed_texts(texts)
        add_chunks(
            chunk_ids=[chunk.id for chunk in batch],
            texts=texts,
            embeddings=embeddings,
            metadatas=[_vector_metadata(doc, chunk) for chunk in batch],
        )

    doc.status = "done"
    doc.chunk_count = len(chunks)
    await db.commit()

    try:
        await rebuild_bm25_index(db)
    except Exception as exc:
        logger.warning("BM25 索引重建失败: %s", exc)


async def rebuild_sparse_index(db: AsyncSession) -> None:
    try:
        await rebuild_bm25_index(db)
    except Exception as exc:
        logger.warning("BM25 索引重建失败: %s", exc)


async def _load_doc_chunks(db: AsyncSession, doc_id: str) -> list[DocChunk]:
    return (await db.execute(
        select(DocChunk)
        .where(DocChunk.doc_id == doc_id)
        .order_by(DocChunk.chunk_index)
    )).scalars().all()


def _vector_metadata(doc: KnowledgeDoc, chunk: DocChunk) -> dict:
    return {
        "doc_id": doc.id,
        "chunk_index": chunk.chunk_index,
        "filename": doc.filename,
        "summary": doc.summary,
        "file_type": doc.file_type,
        "user_id": doc.user_id,
    }
