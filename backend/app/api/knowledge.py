import asyncio
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import GRAPH_ENABLED, MAX_UPLOAD_SIZE
from ..core.database import get_db
from ..models.knowledge import DocChunk, KnowledgeDoc
from ..models.user import User
from ..schemas.knowledge import MergeRequest
from ..services.file_parser import allowed_file, get_file_type
from ..services.graph_service import build_graph_from_doc, delete_doc_graph, get_doc_graph
from ..services.knowledge_chunk_service import delete_chunk, merge_chunks
from ..services.knowledge_document_service import (
    delete_document,
    finalize_document,
    process_document,
    save_upload,
)
from .deps import require_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    category: str = Form(""),
    inspect: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    _validate_upload(file)
    content = await file.read()
    _validate_file_size(content)

    file_type = get_file_type(file.filename)
    file_path = await save_upload(content, file.filename)
    doc = KnowledgeDoc(
        user_id=current_user.id,
        filename=file.filename,
        file_type=file_type,
        file_size=len(content),
        file_path=file_path,
        status="uploading",
        inspect=inspect,
        category=category or None,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    asyncio.create_task(_background_process(doc.id))

    return {
        "code": 0,
        "data": {
            "doc_id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "status": doc.status,
        },
        "message": "上传成功，正在后台处理",
    }


@router.get("/list")
async def list_docs(
    page: int = 1,
    page_size: int = 20,
    category: str = "",
    file_type: str = "",
    status: str = "",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    query = select(KnowledgeDoc).where(KnowledgeDoc.user_id == current_user.id)
    count_query = select(func.count()).select_from(KnowledgeDoc).where(
        KnowledgeDoc.user_id == current_user.id
    )

    query, count_query = _apply_doc_filters(
        query=query,
        count_query=count_query,
        category=category,
        file_type=file_type,
        status=status,
    )

    total = (await db.execute(count_query)).scalar()
    docs = (await db.execute(
        query.order_by(KnowledgeDoc.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return {
        "code": 0,
        "data": {
            "items": [_serialize_doc(doc) for doc in docs],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.put("/chunks/merge")
async def merge_chunks_endpoint(
    req: MergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    try:
        chunks = await merge_chunks(
            db,
            current_user.id,
            req.source_chunk_id,
            req.target_chunk_id,
            req.selected_text,
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    return {"code": 0, "data": {"chunks": [_serialize_chunk(chunk) for chunk in chunks]}}


@router.delete("/chunks/{chunk_id}")
async def delete_chunk_endpoint(
    chunk_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    try:
        chunks = await delete_chunk(db, current_user.id, chunk_id)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    return {"code": 0, "data": {"chunks": [_serialize_chunk(chunk) for chunk in chunks]}}


@router.get("/{doc_id}")
async def get_doc(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    doc = await _get_owned_doc(db, current_user.id, doc_id)
    return {"code": 0, "data": _serialize_doc(doc)}


@router.get("/{doc_id}/chunks")
async def get_doc_chunks(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    await _get_owned_doc(db, current_user.id, doc_id)
    chunks = (await db.execute(
        select(DocChunk)
        .where(DocChunk.doc_id == doc_id)
        .order_by(DocChunk.chunk_index)
    )).scalars().all()
    return {"code": 0, "data": {"chunks": [_serialize_chunk(chunk) for chunk in chunks]}}


@router.post("/{doc_id}/finalize")
async def finalize_doc(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    doc = await _get_owned_doc(db, current_user.id, doc_id)
    try:
        await finalize_document(db, doc)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))
    except Exception as exc:
        logger.exception("文档处理失败 %s: %s", doc.filename, exc)
        doc.status = "failed"
        doc.error_msg = str(exc)
        await db.commit()
        raise HTTPException(500, detail="向量化失败")

    return {"code": 0, "data": {}, "message": "向量化完成"}


@router.delete("/{doc_id}")
async def delete_doc(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    await _get_owned_doc(db, current_user.id, doc_id)
    if GRAPH_ENABLED:
        delete_doc_graph(doc_id, current_user.id)

    deleted = await delete_document(db, current_user.id, doc_id)
    if not deleted:
        raise HTTPException(404, detail="文档不存在")
    return {"code": 0, "data": {"deleted": True, "doc_id": doc_id}}


@router.get("/{doc_id}/graph")
async def get_doc_graph_data(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    _ensure_graph_enabled()
    await _get_owned_doc(db, current_user.id, doc_id)
    return {"code": 0, "data": get_doc_graph(doc_id, current_user.id)}


@router.post("/{doc_id}/build-graph")
async def build_knowledge_graph(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    _ensure_graph_enabled()
    doc = await _get_owned_doc(db, current_user.id, doc_id)
    if doc.status != "done":
        raise HTTPException(400, detail="文档尚未处理完成，无法构建知识图谱")
    if doc.graph_status == "building":
        raise HTTPException(400, detail="知识图谱正在构建中")

    doc.graph_status = "building"
    await db.commit()
    asyncio.create_task(_background_build_graph(doc_id, current_user.id))

    return {
        "code": 0,
        "data": {"doc_id": doc_id, "graph_status": "building"},
        "message": "知识图谱构建已启动",
    }


@router.delete("/{doc_id}/graph")
async def delete_knowledge_graph(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    _ensure_graph_enabled()
    doc = await _get_owned_doc(db, current_user.id, doc_id)

    delete_doc_graph(doc_id, current_user.id)
    doc.graph_status = None
    await db.commit()
    return {"code": 0, "data": {"doc_id": doc_id, "graph_status": None}, "message": "知识图谱已删除"}


async def _background_process(doc_id: str):
    from ..core.database import async_session

    async with async_session() as db:
        doc = await db.get(KnowledgeDoc, doc_id)
        if doc:
            await process_document(db, doc)


async def _background_build_graph(doc_id: str, user_id: str):
    from ..core.database import async_session

    async with async_session() as db:
        await build_graph_from_doc(db, doc_id, user_id)


async def _get_owned_doc(db: AsyncSession, user_id: str, doc_id: str) -> KnowledgeDoc:
    doc = (await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id, KnowledgeDoc.user_id == user_id)
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(404, detail="文档不存在")
    return doc


def _validate_upload(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(400, detail="未选择文件")
    if not allowed_file(file.filename):
        raise HTTPException(400, detail="不支持的文件格式，支持 PDF/Word/Excel/TXT/Markdown/图片")


def _validate_file_size(content: bytes) -> None:
    if len(content) > MAX_UPLOAD_SIZE:
        max_size_mb = MAX_UPLOAD_SIZE // 1024 // 1024
        raise HTTPException(400, detail=f"文件过大，最大 {max_size_mb}MB")


def _ensure_graph_enabled() -> None:
    if not GRAPH_ENABLED:
        raise HTTPException(404, detail="知识图谱功能已关闭")


def _apply_doc_filters(
    *,
    query,
    count_query,
    category: str,
    file_type: str,
    status: str,
):
    if category:
        query = query.where(KnowledgeDoc.category == category)
        count_query = count_query.where(KnowledgeDoc.category == category)
    if file_type:
        query = query.where(KnowledgeDoc.file_type == file_type)
        count_query = count_query.where(KnowledgeDoc.file_type == file_type)
    if status:
        query = query.where(KnowledgeDoc.status == status)
        count_query = count_query.where(KnowledgeDoc.status == status)
    return query, count_query


def _serialize_doc(doc: KnowledgeDoc) -> dict:
    return {
        "doc_id": doc.id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "char_count": doc.char_count,
        "category": doc.category,
        "graph_status": doc.graph_status,
        "error_msg": doc.error_msg,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


def _serialize_chunk(chunk: DocChunk) -> dict:
    return {
        "chunk_id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "char_count": chunk.char_count,
    }
