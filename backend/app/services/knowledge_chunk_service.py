from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.knowledge import DocChunk, KnowledgeDoc
from .knowledge_chunking import hash_text


async def delete_chunk(db: AsyncSession, user_id: str, chunk_id: str) -> list[DocChunk]:
    chunk = await db.get(DocChunk, chunk_id)
    if not chunk:
        raise ValueError("分块不存在")

    doc = await _get_chunk_doc(db, user_id, chunk.doc_id)
    _ensure_inspecting(doc)

    await db.delete(chunk)
    await db.flush()
    remaining = await _renumber_chunks(db, doc.id)
    await db.commit()
    return remaining


async def merge_chunks(
    db: AsyncSession,
    user_id: str,
    source_chunk_id: str,
    target_chunk_id: str,
    selected_text: str | None = None,
) -> list[DocChunk]:
    source = await db.get(DocChunk, source_chunk_id)
    target = await db.get(DocChunk, target_chunk_id)
    _validate_merge_source_and_target(source, target)

    doc = await _get_chunk_doc(db, user_id, source.doc_id)
    _ensure_inspecting(doc)

    if selected_text and selected_text.strip():
        await _merge_selected_text(db, source, target, selected_text.strip())
    else:
        await _merge_whole_chunk(db, source, target)

    remaining = await _renumber_chunks(db, doc.id)
    await db.commit()
    return remaining


async def _get_chunk_doc(db: AsyncSession, user_id: str, doc_id: str) -> KnowledgeDoc:
    doc = (await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id, KnowledgeDoc.user_id == user_id)
    )).scalar_one_or_none()
    if not doc:
        raise ValueError("分块不存在")
    return doc


def _ensure_inspecting(doc: KnowledgeDoc) -> None:
    if doc.status != "inspecting":
        raise ValueError("文档不在审查状态")


def _validate_merge_source_and_target(source: DocChunk | None, target: DocChunk | None) -> None:
    if not source or not target:
        raise ValueError("源分块或目标分块不存在")
    if source.id == target.id:
        raise ValueError("源分块和目标分块不能相同")
    if source.doc_id != target.doc_id:
        raise ValueError("分块不属于同一文档")
    if abs(source.chunk_index - target.chunk_index) != 1:
        raise ValueError("只能合并相邻分块")


async def _merge_selected_text(
    db: AsyncSession,
    source: DocChunk,
    target: DocChunk,
    selected_text: str,
) -> None:
    if selected_text not in source.content:
        raise ValueError("选中的文本不在源分块中")

    source_above = source.chunk_index < target.chunk_index
    if source_above:
        target.content = selected_text + "\n\n" + target.content.lstrip()
    else:
        target.content = target.content.rstrip() + "\n\n" + selected_text
    _refresh_chunk_hash(target)

    source.content = source.content.replace(selected_text, "", 1).strip()
    source.char_count = len(source.content)
    if source.content:
        source.content_hash = hash_text(source.content)
    else:
        await db.delete(source)
        await db.flush()


async def _merge_whole_chunk(db: AsyncSession, source: DocChunk, target: DocChunk) -> None:
    source_above = source.chunk_index < target.chunk_index
    if source_above:
        target.content = source.content.strip() + "\n\n" + target.content.lstrip()
    else:
        target.content = target.content.rstrip() + "\n\n" + source.content.strip()

    _refresh_chunk_hash(target)
    await db.delete(source)
    await db.flush()


async def _renumber_chunks(db: AsyncSession, doc_id: str) -> list[DocChunk]:
    chunks = (await db.execute(
        select(DocChunk)
        .where(DocChunk.doc_id == doc_id)
        .order_by(DocChunk.chunk_index)
    )).scalars().all()

    for index, chunk in enumerate(chunks):
        chunk.chunk_index = index
        if chunk.chunk_metadata:
            chunk.chunk_metadata["chunk_index"] = index
            chunk.chunk_metadata["char_count"] = chunk.char_count

    return chunks


def _refresh_chunk_hash(chunk: DocChunk) -> None:
    chunk.char_count = len(chunk.content)
    chunk.content_hash = hash_text(chunk.content)
