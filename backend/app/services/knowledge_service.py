"""知识库核心服务 — 解析 → 摘要 → 分块(按类型) → 向量化 → 存储"""

from __future__ import annotations
import hashlib
import logging
import os
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sa_delete
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from ..core.config import (
    UPLOAD_DIR, CHUNK_SIZE, CHUNK_OVERLAP,
    BAILIAN_API_KEY, BAILIAN_BASE_URL,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL,
    SUMMARY_MODEL, MULTIMODAL_MODEL, SUMMARY_MAX_CHARS,
)
from ..core.prompts import SUMMARY_PROMPT, MULTIMODAL_PROMPT
from ..models.knowledge import KnowledgeDoc, DocChunk
from .file_parser import (
    parse_file, ParseResult,
    encode_image_base64, get_image_mime, encode_pdf_pages_as_images,
)
from .embedding import embed_texts
from .vector_store import add_chunks, delete_by_doc_id
from .bm25_store import rebuild_bm25_index

logger = logging.getLogger(__name__)

BATCH_SIZE = 10


def _build_llm(model: str, temperature: float = 0.3, max_tokens: int = 200,
               api_key: str = BAILIAN_API_KEY, base_url: str = BAILIAN_BASE_URL) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
        base_url=base_url,
    )

EXCEL_CHUNK_HEADER_ROWS = 2


def _hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _make_chunk_meta(doc: KnowledgeDoc, chunk_index: int, char_count: int, structure: str) -> dict:
    return {
        "source": doc.filename,
        "chunk_index": chunk_index,
        "char_count": char_count,
        "summary": doc.summary,
        "file_type": doc.file_type,
        "structure": structure,
        "user_id": doc.user_id,
    }


# =========================== 多模态解析 ===========================

async def _parse_with_multimodal(file_path: str, file_type: str, filename: str) -> str:
    """使用 qwen3.6-flash 多模态模型提取图片/扫描件中的文字"""
    llm = _build_llm(MULTIMODAL_MODEL, max_tokens=2000)

    if file_type == "pdf":
        page_images = encode_pdf_pages_as_images(file_path)
        if not page_images:
            raise ValueError("PDF 页面渲染失败")
        all_texts = []
        for idx, b64 in enumerate(page_images):
            msg = HumanMessage(content=[
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": f"这是文档《{filename}》的第 {idx+1} 页。{MULTIMODAL_PROMPT}"},
            ])
            resp = llm.invoke([msg])
            if resp.content:
                all_texts.append(resp.content.strip())
        return "\n\n".join(all_texts)

    b64 = encode_image_base64(file_path)
    mime = get_image_mime(file_path)
    msg = HumanMessage(content=[
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        {"type": "text", "text": f"图片文件名: {filename}\n{MULTIMODAL_PROMPT}"},
    ])
    resp = llm.invoke([msg])
    return resp.content.strip()


# =========================== 文档摘要 ===========================

async def _summarize_document(text: str, filename: str) -> str:
    snippet = text[:SUMMARY_MAX_CHARS]
    prompt = SUMMARY_PROMPT.format(text=snippet)
    try:
        llm = _build_llm(SUMMARY_MODEL, api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        resp = llm.invoke(prompt)
        summary = resp.content.strip()
        logger.info("文档 %s 摘要: %s", filename, summary)
        return summary
    except Exception as e:
        logger.warning("文档摘要失败 %s: %s", filename, e)
        return f"文档: {filename}"


# =========================== 分块策略 ===========================

def _chunk_semantic(text: str) -> list[str]:
    """语义分块 — PDF / Word / TXT / 图片多模态结果"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " ", ""],
    )
    return splitter.split_text(text)


def _chunk_markdown(text: str) -> list[str]:
    """Markdown 按标题分块 — 每个标题+正文为一个 chunk"""
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
        for d in docs:
            header = ""
            if d.metadata:
                parts = [v for k, v in d.metadata.items() if v]
                if parts:
                    header = " > ".join(parts) + "\n"
            chunk_text = header + d.page_content
            if len(chunk_text) > CHUNK_SIZE * 3:
                # 超长大段再切分
                sub = RecursiveCharacterTextSplitter(
                    chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
                    separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " ", ""],
                )
                subs = sub.split_text(chunk_text)
                chunks.extend(subs)
            else:
                chunks.append(chunk_text)
        return chunks if chunks else _chunk_semantic(text)
    except Exception as e:
        logger.warning("Markdown 分块失败，回退语义分块: %s", e)
        return _chunk_semantic(text)


def _chunk_excel(text: str) -> list[str]:
    """Excel 按行分块 — 每个 Sheet 的表头行 + 数据行组合"""
    sheets = text.split("## Sheet: ")
    chunks = []
    for sheet_block in sheets:
        if not sheet_block.strip():
            continue
        lines = [l for l in sheet_block.strip().split("\n") if l.strip()]
        if len(lines) <= EXCEL_CHUNK_HEADER_ROWS:
            chunks.append(sheet_block.strip())
            continue

        sheet_name = lines[0]
        header = "\n".join(lines[1:EXCEL_CHUNK_HEADER_ROWS + 1])
        data_rows = lines[EXCEL_CHUNK_HEADER_ROWS + 1:]

        # 每约 20 行数据为一个 chunk
        chunk_size_rows = max(1, (CHUNK_SIZE // max(1, len(header.split("\n")[0]))) * 10)

        for i in range(0, len(data_rows), chunk_size_rows):
            batch = data_rows[i:i + chunk_size_rows]
            chunk_text = f"Sheet: {sheet_name}\n{header}\n" + "\n".join(batch)
            chunks.append(chunk_text)
    return chunks


CHUNKERS = {
    "semantic": _chunk_semantic,
    "excel": _chunk_excel,
    "markdown": _chunk_markdown,
}


# =========================== 保存上传文件 ===========================

async def save_upload(file_bytes: bytes, filename: str) -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    return file_path


# =========================== 核心流水线 ===========================

async def process_document(db: AsyncSession, doc: KnowledgeDoc):
    """解析 → (多模态) → 摘要 → 分块(按类型) → 向量化"""
    try:
        # 1. 解析
        doc.status = "parsing"
        await db.commit()

        parsed: ParseResult = parse_file(doc.file_path, doc.file_type)

        # 1.1 如果需要多模态提取（扫描件PDF / 图片）
        if parsed.needs_multimodal:
            doc.status = "parsing"  # 保持 parsing 状态
            await db.commit()
            parsed.text = await _parse_with_multimodal(doc.file_path, doc.file_type, doc.filename)
            parsed.structure = "semantic"

        if not parsed.text.strip():
            raise ValueError("文件内容为空或无法解析")

        doc.char_count = len(parsed.text)

        # 2. 生成摘要
        doc.summary = await _summarize_document(parsed.text, doc.filename)
        doc.status = "chunking"
        await db.commit()

        # 3. 按文档类型分块
        chunker = CHUNKERS.get(parsed.structure, _chunk_semantic)
        raw_chunks = chunker(parsed.text)
        logger.info("文档 %s (type=%s structure=%s): %d chunks",
                     doc.filename, doc.file_type, parsed.structure, len(raw_chunks))

        # 4. 去重 + 入库
        new_chunks = []
        skipped = 0
        for i, chunk_text in enumerate(raw_chunks):
            if not chunk_text.strip():
                continue
            h = _hash(chunk_text)
            existing = (await db.execute(
                select(DocChunk.id).where(DocChunk.content_hash == h)
            )).scalar_one_or_none()
            if existing:
                skipped += 1
                continue
            chunk = DocChunk(
                doc_id=doc.id,
                chunk_index=i,
                content=chunk_text,
                content_hash=h,
                char_count=len(chunk_text),
                chunk_metadata=_make_chunk_meta(doc, i, len(chunk_text), parsed.structure),
            )
            db.add(chunk)
            new_chunks.append(chunk)

        await db.commit()

        if not new_chunks:
            raise ValueError(f"所有 {len(raw_chunks)} 个分块均已存在（去重跳过 {skipped} 个）")

        doc.chunk_count = len(new_chunks)
        logger.info("文档 %s: %d chunks 入库 (去重跳过 %d)", doc.filename, len(new_chunks), skipped)

        # 5. 审查模式：暂停，等待用户确认
        if doc.inspect:
            doc.status = "inspecting"
            await db.commit()
            logger.info("文档 %s: 进入审查模式，等待用户确认", doc.filename)
            return

        await _embed_and_finalize(db, doc, new_chunks)

    except Exception as e:
        logger.exception("文档处理失败 %s: %s", doc.filename, e)
        doc.status = "failed"
        doc.error_msg = str(e)
        await db.commit()


async def _embed_and_finalize(db: AsyncSession, doc: KnowledgeDoc, chunks: list[DocChunk] | None = None):
    """向量化 + 完成。chunks 为 None 时从 DB 重新读取（审查合并后的情况）"""
    doc.status = "embedding"
    await db.commit()

    if chunks is None:
        chunks = (await db.execute(
            select(DocChunk).where(DocChunk.doc_id == doc.id).order_by(DocChunk.chunk_index)
        )).scalars().all()

    if not chunks:
        raise ValueError("没有找到要嵌入的分块")

    for batch_start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[batch_start:batch_start + BATCH_SIZE]
        texts = [c.content for c in batch]
        embeddings = await embed_texts(texts)
        add_chunks(
            chunk_ids=[c.id for c in batch],
            texts=texts,
            embeddings=embeddings,
            metadatas=[{
                "doc_id": doc.id,
                "chunk_index": c.chunk_index,
                "filename": doc.filename,
                "summary": doc.summary,
                "file_type": doc.file_type,
                "user_id": doc.user_id,
            } for c in batch],
        )

    doc.status = "done"
    doc.chunk_count = len(chunks)
    await db.commit()

    try:
        await rebuild_bm25_index(db)
    except Exception as e:
        logger.warning("BM25 索引重建失败: %s", e)


async def finalize_document(db: AsyncSession, doc: KnowledgeDoc):
    """审查通过后继续向量化"""
    if doc.status != "inspecting":
        raise ValueError(f"文档状态为 '{doc.status}'，无法继续，需要 'inspecting' 状态")
    await _embed_and_finalize(db, doc)


async def delete_chunk(db: AsyncSession, chunk_id: str) -> list[DocChunk]:
    """删除单个分块，重新编号剩余分块"""
    chunk = await db.get(DocChunk, chunk_id)
    if not chunk:
        raise ValueError("分块不存在")

    doc = await db.get(KnowledgeDoc, chunk.doc_id)
    if doc.status != "inspecting":
        raise ValueError("文档不在审查状态")

    await db.delete(chunk)
    await db.flush()

    remaining = (await db.execute(
        select(DocChunk)
        .where(DocChunk.doc_id == doc.id)
        .order_by(DocChunk.chunk_index)
    )).scalars().all()

    for i, c in enumerate(remaining):
        c.chunk_index = i
        if c.chunk_metadata:
            c.chunk_metadata["chunk_index"] = i

    await db.commit()
    return remaining


async def merge_chunks(
    db: AsyncSession,
    source_chunk_id: str,
    target_chunk_id: str,
    selected_text: str | None = None,
) -> list[DocChunk]:
    """将 source 块的全部或选中内容追加到 target 块。若 source 变空则删除。"""
    source = await db.get(DocChunk, source_chunk_id)
    target = await db.get(DocChunk, target_chunk_id)

    if not source or not target:
        raise ValueError("源分块或目标分块不存在")
    if source.id == target.id:
        raise ValueError("源分块和目标分块不能相同")
    if source.doc_id != target.doc_id:
        raise ValueError("分块不属于同一文档")

    # 只能合并相邻分块
    if abs(source.chunk_index - target.chunk_index) != 1:
        raise ValueError("只能合并相邻分块")

    doc = await db.get(KnowledgeDoc, source.doc_id)
    if doc.status != "inspecting":
        raise ValueError("文档不在审查状态")

    # source 在上方 → 内容放到 target 顶部；source 在下方 → 放到 target 底部
    source_above = source.chunk_index < target.chunk_index

    is_partial = bool(selected_text and selected_text.strip())

    if is_partial:
        if selected_text not in source.content:
            raise ValueError("选中的文本不在源分块中")
        moved = selected_text.strip()
        if source_above:
            target.content = moved + "\n\n" + target.content.lstrip()
        else:
            target.content = target.content.rstrip() + "\n\n" + moved
        target.char_count = len(target.content)
        target.content_hash = _hash(target.content)
        # 从 source 中移除选中文本
        source.content = source.content.replace(selected_text, "", 1).strip()
        source.char_count = len(source.content)
        if source.content:
            source.content_hash = _hash(source.content)
        else:
            await db.delete(source)
            await db.flush()
    else:
        if source_above:
            target.content = source.content.strip() + "\n\n" + target.content.lstrip()
        else:
            target.content = target.content.rstrip() + "\n\n" + source.content.strip()
        target.char_count = len(target.content)
        target.content_hash = _hash(target.content)
        await db.delete(source)
        await db.flush()

    # 重新编号剩余分块
    remaining = (await db.execute(
        select(DocChunk)
        .where(DocChunk.doc_id == doc.id)
        .order_by(DocChunk.chunk_index)
    )).scalars().all()

    for i, c in enumerate(remaining):
        c.chunk_index = i
        if c.chunk_metadata:
            c.chunk_metadata["chunk_index"] = i
            c.chunk_metadata["char_count"] = c.char_count

    await db.commit()
    return remaining


# =========================== 删除文档 ===========================

async def delete_document(db: AsyncSession, doc_id: str) -> bool:
    doc = await db.get(KnowledgeDoc, doc_id)
    if not doc:
        return False

    delete_by_doc_id(doc_id)
    await db.execute(sa_delete(DocChunk).where(DocChunk.doc_id == doc_id))

    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except OSError:
            pass

    await db.delete(doc)
    await db.commit()

    # 重建 BM25 稀疏索引
    try:
        await rebuild_bm25_index(db)
    except Exception as e:
        logger.warning("BM25 索引重建失败: %s", e)

    return True
