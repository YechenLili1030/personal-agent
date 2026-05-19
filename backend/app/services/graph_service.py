"""Neo4j 知识图谱服务 — 连接管理 + 实体抽取 + 图谱写入/查询/删除"""

from __future__ import annotations
import json
import logging
from collections import defaultdict

from neo4j import GraphDatabase, Driver
from openai import OpenAI
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import (
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, GRAPH_EXTRACT_MODEL,
)
from ..core.prompts import GRAPH_EXTRACT_PROMPT

logger = logging.getLogger(__name__)

_driver: Driver | None = None


def _get_driver() -> Driver:
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        _driver.verify_connectivity()
        logger.info("Neo4j 已连接: %s", NEO4J_URI)
    return _driver


def _get_llm() -> OpenAI:
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


# ═══════════════════════ 构建图谱 ═══════════════════════

async def build_graph_from_doc(db: AsyncSession, doc_id: str, user_id: str):
    """从文档 chunk 中抽取实体/关系并写入 Neo4j"""
    from ..models.knowledge import DocChunk, KnowledgeDoc

    try:
        # 1. 读取文档所有 chunks
        rows = (await db.execute(
            sa_select(DocChunk.content)
            .where(DocChunk.doc_id == doc_id)
            .order_by(DocChunk.chunk_index)
        )).scalars().all()

        if not rows:
            raise ValueError("文档无分块数据")

        full_text = "\n\n".join(rows)
        logger.info("图谱构建: doc_id=%s len=%d chunks=%d", doc_id, len(full_text), len(rows))

        # 2. 调用 qwen-plus 抽取实体和关系
        data = _extract_entities_and_relations(full_text)
        entities = data.get("entities", [])
        relations = data.get("relations", [])

        if not entities:
            logger.info("文档 %s 未抽取到实体，跳过图谱构建", doc_id)
            return

        logger.info("抽取结果: entities=%d relations=%d", len(entities), len(relations))

        # 3. 写入 Neo4j
        driver = _get_driver()
        _insert_to_neo4j(driver, entities, relations, doc_id, user_id)

        # 4. 标记完成
        doc = await db.get(KnowledgeDoc, doc_id)
        if doc:
            doc.graph_status = "built"
            await db.commit()

        logger.info("图谱构建完成: doc_id=%s nodes=%d edges=%d", doc_id, len(entities), len(relations))

    except Exception as e:
        logger.exception("图谱构建失败 doc_id=%s: %s", doc_id, e)
        from ..models.knowledge import KnowledgeDoc
        doc = await db.get(KnowledgeDoc, doc_id)
        if doc:
            doc.graph_status = "failed"
            await db.commit()
        raise


def _extract_entities_and_relations(text: str) -> dict:
    """用百炼 qwen-plus 从文本中抽取实体和关系"""
    llm = _get_llm()
    prompt = GRAPH_EXTRACT_PROMPT.format(text=text[:10000])

    resp = llm.chat.completions.create(
        model=GRAPH_EXTRACT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        extra_body={"thinking": {"type": "disabled"}},
    )
    raw = (resp.choices[0].message.content or "").strip()
    logger.debug("LLM 图谱抽取原始响应: %s", raw[:300])

    return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    """鲁棒 JSON 解析，处理 LLM 输出的各种格式问题"""
    # 1. 去除 markdown 代码块包装
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # 去掉 ```json 或 ``` 开头
        if lines[0].startswith("```"):
            lines = lines[1:]
        # 去掉末尾 ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # 2. 尝试直接解析
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. 尝试修复常见问题后解析
    fixed = _repair_json(cleaned)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError as e:
        logger.error("JSON 解析失败，已尝试修复。原始响应(前500字): %s", cleaned[:500])
        logger.error("JSON 错误: %s", e)
        return {"entities": [], "relations": []}


def _repair_json(raw: str) -> str:
    """修复 LLM 输出中常见的 JSON 格式错误"""
    import re

    text = raw.strip()

    # 去除尾部逗号 (最常见的错误: "xxx",] 或 "xxx",})
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # 去除注释行 (// ... 或 # ...)
    text = re.sub(r"^\s*(//|#).*$", "", text, flags=re.MULTILINE)

    # 修复单引号 JSON（LLM 偶尔用单引号）
    # 只在明显是单引号 JSON 时才转换
    if text.count("'") > text.count('"') * 2:
        # 保守策略：只替换键和值的单引号
        text = re.sub(r"'([^']*)'(?=\s*:)", r'"\1"', text)  # 键
        text = re.sub(r":\s*'([^']*)'", r': "\1"', text)     # 值

    # 确保 JSON 以 { 开始
    start = text.find("{")
    if start > 0:
        text = text[start:]

    # 确保 JSON 以 } 结束（找到最后一个配对的 }）
    end = text.rfind("}")
    if end > 0 and end < len(text) - 1:
        text = text[:end + 1]

    return text


def _insert_to_neo4j(driver: Driver, entities: list[dict], relations: list[dict],
                     doc_id: str, user_id: str):
    """将实体和关系写入 Neo4j"""
    with driver.session() as session:
        # 先 MERGE 所有实体节点
        for e in entities:
            session.run(
                """
                MERGE (n:Entity {name: $name, user_id: $user_id})
                SET n.type = $type,
                    n.doc_id = CASE WHEN n.doc_id IS NULL THEN $doc_id
                                    ELSE n.doc_id + ';' + $doc_id END
                """,
                name=e["name"], type=e.get("type", "概念"),
                doc_id=doc_id, user_id=user_id,
            )

        # 再 CREATE 关系
        for r in relations:
            head = r.get("head", "")
            tail = r.get("tail", "")
            rel_type = r.get("relation", "相关")
            if not head or not tail:
                continue
            rel_type_clean = rel_type.replace(" ", "_").replace("-", "_")
            session.run(
                f"""
                MATCH (a:Entity {{name: $head, user_id: $user_id}})
                MATCH (b:Entity {{name: $tail, user_id: $user_id}})
                MERGE (a)-[r:{rel_type_clean}]->(b)
                """,
                head=head, tail=tail, user_id=user_id,
            )


# ═══════════════════════ 图谱查询 ═══════════════════════

def query_graph(entity_names: list[str], user_id: str) -> list[dict]:
    """从实体名出发，查询 1-hop 子图。返回 [{"head", "relation", "tail"}, ...]"""
    if not entity_names:
        return []

    try:
        driver = _get_driver()
    except Exception as e:
        logger.warning("Neo4j 连接失败: %s", e)
        return []

    with driver.session() as session:
        result = session.run(
            """
            MATCH (e1:Entity {user_id: $user_id})
            WHERE e1.name IN $names
            MATCH (e1)-[r]-(e2:Entity {user_id: $user_id})
            RETURN e1.name AS head, type(r) AS relation, e2.name AS tail,
                   e1.type AS head_type, e2.type AS tail_type
            LIMIT 30
            """,
            names=entity_names, user_id=user_id,
        )
        return [record.data() for record in result]


# ═══════════════════════ 图谱可视化数据 ═══════════════════════

def get_doc_graph(doc_id: str) -> dict:
    """获取文档的完整图谱数据（节点 + 边），供前端可视化"""
    try:
        driver = _get_driver()
    except Exception as e:
        logger.warning("Neo4j 连接失败: %s", e)
        return {"nodes": [], "edges": []}

    with driver.session() as session:
        # 查属于该文档的所有实体
        nodes_result = session.run(
            """
            MATCH (e:Entity)
            WHERE e.doc_id CONTAINS $doc_id
            RETURN DISTINCT e.name AS name, e.type AS type
            """,
            doc_id=doc_id,
        )
        nodes = [{"name": r["name"], "type": r["type"]} for r in nodes_result]

        # 查这些实体之间的关系
        edges_result = session.run(
            """
            MATCH (e1:Entity)-[r]->(e2:Entity)
            WHERE e1.doc_id CONTAINS $doc_id AND e2.doc_id CONTAINS $doc_id
            RETURN e1.name AS source, type(r) AS relation, e2.name AS target
            """,
            doc_id=doc_id,
        )
        edges = [{"source": r["source"], "relation": r["relation"], "target": r["target"]} for r in edges_result]

        logger.info("图谱可视化数据: doc_id=%s nodes=%d edges=%d", doc_id, len(nodes), len(edges))
        return {"nodes": nodes, "edges": edges}


# ═══════════════════════ 图谱删除 ═══════════════════════

def delete_doc_graph(doc_id: str):
    """删除与文档关联的所有实体和关系"""
    try:
        driver = _get_driver()
    except Exception as e:
        logger.warning("Neo4j 连接失败，跳过图谱删除: %s", e)
        return

    with driver.session() as session:
        # 删除仅属于该文档的关系（避免误删共享实体）
        session.run(
            """
            MATCH (e:Entity)
            WHERE e.doc_id = $doc_id
            DETACH DELETE e
            """,
            doc_id=doc_id,
        )
        logger.info("已删除文档 %s 的图谱数据", doc_id)
