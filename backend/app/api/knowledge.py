import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select, func

from ..core.database import get_db
from ..core.config import MAX_UPLOAD_SIZE
from ..models.knowledge import KnowledgeDoc, DocChunk
from ..models.user import User
from ..schemas.knowledge import MergeRequest
from ..services.file_parser import allowed_file, get_file_type
from ..services.knowledge_service import (
    save_upload, process_document, delete_document,
    merge_chunks, delete_chunk, finalize_document,
)
from ..services.graph_service import build_graph_from_doc, delete_doc_graph, get_doc_graph
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
    if not file.filename:
        raise HTTPException(400, detail="未选择文件")
    if not allowed_file(file.filename):
        raise HTTPException(400, detail=f"不支持的文件格式，支持: PDF/Word/Excel/TXT/Markdown/图片")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, detail=f"文件过大，最大 {MAX_UPLOAD_SIZE // 1024 // 1024}MB")

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

    # 异步后台处理
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


async def _background_process(doc_id: str):
    """后台处理文档"""
    from ..core.database import async_session
    async with async_session() as db:
        doc = await db.get(KnowledgeDoc, doc_id)
        if doc:
            await process_document(db, doc)


@router.get("/list")
async def list_docs(
    page: int = 1,
    page_size: int = 20,
    category: str = "",
    file_type: str = "",
    status: str = "",
    db: AsyncSession = Depends(get_db),
):
    query = select(KnowledgeDoc)
    count_q = select(func.count()).select_from(KnowledgeDoc)

    if category:
        query = query.where(KnowledgeDoc.category == category)
        count_q = count_q.where(KnowledgeDoc.category == category)
    if file_type:
        query = query.where(KnowledgeDoc.file_type == file_type)
        count_q = count_q.where(KnowledgeDoc.file_type == file_type)
    if status:
        query = query.where(KnowledgeDoc.status == status)
        count_q = count_q.where(KnowledgeDoc.status == status)

    total = (await db.execute(count_q)).scalar()
    query = query.order_by(KnowledgeDoc.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()

    items = [{
        "doc_id": d.id,
        "filename": d.filename,
        "file_type": d.file_type,
        "file_size": d.file_size,
        "status": d.status,
        "chunk_count": d.chunk_count,
        "char_count": d.char_count,
        "category": d.category,
        "graph_status": d.graph_status,
        "error_msg": d.error_msg,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    } for d in rows]

    return {
        "code": 0,
        "data": {"items": items, "total": total, "page": page, "page_size": page_size},
    }


@router.put("/chunks/merge")
async def merge_chunks_endpoint(
    req: MergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    try:
        chunks = await merge_chunks(db, req.source_chunk_id, req.target_chunk_id, req.selected_text)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    return {
        "code": 0,
        "data": {
            "chunks": [{
                "chunk_id": c.id,
                "chunk_index": c.chunk_index,
                "content": c.content,
                "char_count": c.char_count,
            } for c in chunks],
        },
    }


@router.delete("/chunks/{chunk_id}")
async def delete_chunk_endpoint(
    chunk_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    try:
        chunks = await delete_chunk(db, chunk_id)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    return {
        "code": 0,
        "data": {
            "chunks": [{
                "chunk_id": c.id,
                "chunk_index": c.chunk_index,
                "content": c.content,
                "char_count": c.char_count,
            } for c in chunks],
        },
    }


@router.get("/{doc_id}")
async def get_doc(doc_id: str, db: AsyncSession = Depends(get_db)):
    doc = await db.get(KnowledgeDoc, doc_id)
    if not doc:
        raise HTTPException(404, detail="文档不存在")
    return {
        "code": 0,
        "data": {
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
        },
    }


@router.get("/{doc_id}/chunks")
async def get_doc_chunks(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    doc = await db.get(KnowledgeDoc, doc_id)
    if not doc:
        raise HTTPException(404, detail="文档不存在")

    chunks = (await db.execute(
        select(DocChunk)
        .where(DocChunk.doc_id == doc_id)
        .order_by(DocChunk.chunk_index)
    )).scalars().all()

    return {
        "code": 0,
        "data": {
            "chunks": [{
                "chunk_id": c.id,
                "chunk_index": c.chunk_index,
                "content": c.content,
                "char_count": c.char_count,
            } for c in chunks],
        },
    }


@router.post("/{doc_id}/finalize")
async def finalize_doc(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    doc = await db.get(KnowledgeDoc, doc_id)
    if not doc:
        raise HTTPException(404, detail="文档不存在")

    try:
        await finalize_document(db, doc)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    except Exception as e:
        logger.exception("文档处理失败 %s: %s", doc.filename, e)
        doc.status = "failed"
        doc.error_msg = str(e)
        await db.commit()
        raise HTTPException(500, detail="向量化失败")

    return {"code": 0, "data": {}, "message": "向量化完成"}


@router.delete("/{doc_id}")
async def delete_doc(doc_id: str, db: AsyncSession = Depends(get_db)):
    # 同时删除关联的知识图谱
    delete_doc_graph(doc_id)
    deleted = await delete_document(db, doc_id)
    if not deleted:
        raise HTTPException(404, detail="文档不存在")
    return {"code": 0, "data": {"deleted": True, "doc_id": doc_id}}


@router.get("/{doc_id}/graph")
async def get_doc_graph_data(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取文档的知识图谱数据（节点和边），供前端可视化"""
    doc = await db.get(KnowledgeDoc, doc_id)
    if not doc:
        raise HTTPException(404, detail="文档不存在")
    data = get_doc_graph(doc_id)
    return {"code": 0, "data": data}


@router.post("/{doc_id}/build-graph")
async def build_knowledge_graph(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """为指定文档构建知识图谱"""
    doc = await db.get(KnowledgeDoc, doc_id)
    if not doc:
        raise HTTPException(404, detail="文档不存在")
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


async def _background_build_graph(doc_id: str, user_id: str):
    """后台构建知识图谱"""
    from ..core.database import async_session
    async with async_session() as db:
        await build_graph_from_doc(db, doc_id, user_id)


@router.delete("/{doc_id}/graph")
async def delete_knowledge_graph(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """删除指定文档的知识图谱数据"""
    doc = await db.get(KnowledgeDoc, doc_id)
    if not doc:
        raise HTTPException(404, detail="文档不存在")

    delete_doc_graph(doc_id)
    doc.graph_status = None
    await db.commit()

    return {"code": 0, "data": {"doc_id": doc_id, "graph_status": None}, "message": "知识图谱已删除"}
