"""知识图谱检索 — 从 RAG 结果提取实体 → 查图 → 格式化上下文"""

from __future__ import annotations
import json
import logging
from collections import Counter

import jieba
import jieba.posseg as pseg
from openai import OpenAI

from ..core.config import BAILIAN_API_KEY, BAILIAN_BASE_URL, GRAPH_EXTRACT_MODEL
from ..core.prompts import GRAPH_ENTITY_PROMPT
from .graph_service import query_graph

logger = logging.getLogger(__name__)

# jieba 词性标签 → 可能为实体的标签
ENTITY_POS_TAGS = {"nr", "ns", "nt", "nz", "nrfg", "nrt"}


def _get_llm() -> OpenAI:
    return OpenAI(api_key=BAILIAN_API_KEY, base_url=BAILIAN_BASE_URL)


# ═══════════════════════ 实体抽取 (混合策略) ═══════════════════════

def extract_entities_from_chunks(chunks: list[dict]) -> list[str]:
    """
    从检索到的 chunks 中提取关键实体。混合策略：
    1. jieba 词性标注 → 提取专有名词 → 按频率排序取 top-8
    2. 如果 < 2 个，用 qwen-plus 兜底提取 3-5 个
    3. 去重后截断到 5 个
    """
    if not chunks:
        return []

    # ── 策略 1: jieba 词性标注 ──
    jieba_entities = _extract_entities_jieba(chunks)

    if len(jieba_entities) >= 2:
        logger.info("jieba 实体提取: %s", jieba_entities)
        return jieba_entities[:5]

    # ── 策略 2: LLM 兜底 ──
    logger.info("jieba 实体不足 (%d 个)，使用 qwen-plus 兜底", len(jieba_entities))
    try:
        llm_entities = _extract_entities_llm(chunks)
        all_entities = list(dict.fromkeys(jieba_entities + llm_entities))
        logger.info("LLM 实体提取: %s → 合并后: %s", llm_entities, all_entities)
        return all_entities[:5]
    except Exception as e:
        logger.warning("LLM 实体提取失败: %s", e)
        return jieba_entities[:5]


def _extract_entities_jieba(chunks: list[dict]) -> list[str]:
    """用 jieba 词性标注提取专有名词"""
    word_freq: Counter = Counter()

    for c in chunks:
        text = c.get("content", "")
        for pair in pseg.cut(text):
            word = pair.word.strip()
            if len(word) >= 2 and pair.flag in ENTITY_POS_TAGS:
                word_freq[word] += 1

    # 按频率排序，取 top-8
    return [w for w, _ in word_freq.most_common(8)]


def _extract_entities_llm(chunks: list[dict]) -> list[str]:
    """用 qwen-plus 从 chunks 中提取核心实体"""
    # 拼接 chunks 文本（截断以确保不超 token 限制）
    texts = []
    total = 0
    for c in chunks:
        content = c.get("content", "")
        if total + len(content) > 3000:
            texts.append(content[:3000 - total])
            break
        texts.append(content)
        total += len(content)

    combined = "\n\n".join(texts)
    prompt = GRAPH_ENTITY_PROMPT.format(text=combined)

    llm = _get_llm()
    resp = llm.chat.completions.create(
        model=GRAPH_EXTRACT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=200,
    )
    raw = resp.choices[0].message.content.strip()

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    entities = json.loads(raw)
    if isinstance(entities, list):
        return [e for e in entities if isinstance(e, str) and len(e) >= 2]
    return []


# ═══════════════════════ 图谱上下文构建 ═══════════════════════

def retrieve_graph_context(entity_names: list[str], user_id: str) -> str:
    """
    用实体名查询 Neo4j 知识图谱，格式化为自然语言。
    返回空字符串表示无图谱结果。
    """
    if not entity_names:
        return ""

    try:
        triples = query_graph(entity_names, user_id)
    except Exception as e:
        logger.warning("图谱查询失败: %s", e)
        return ""

    if not triples:
        logger.info("图谱无结果: entities=%s", entity_names)
        return ""

    # 格式化为易读文本
    lines = ["【知识图谱 · 关联信息】"]
    seen: set[str] = set()
    for t in triples:
        key = f"{t['head']}-{t['relation']}-{t['tail']}"
        if key not in seen:
            seen.add(key)
            lines.append(f"- {t['head']} → {t['relation']} → {t['tail']}")

    logger.info("图谱检索: entities=%s → triples=%d", entity_names, len(triples))
    return "\n".join(lines)


def retrieve_graph_raw(entity_names: list[str], user_id: str) -> list[dict]:
    """原始图谱查询（返回结构化数据，用于调试）"""
    if not entity_names:
        return []
    try:
        return query_graph(entity_names, user_id)
    except Exception:
        return []
