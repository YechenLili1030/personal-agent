"""意图识别 — 百炼 tongyi-intent-detect-v3 专用模型

只做一件事：判断用户问题是否需要 RAG 检索。
工具调用由 ReAct 循环自行决策，不受意图识别干预。
"""

from __future__ import annotations
import logging
from openai import OpenAI

from ..core.config import BAILIAN_API_KEY, BAILIAN_BASE_URL, INTENT_MODEL

logger = logging.getLogger(__name__)

# 意图 → 是否触发 RAG 检索
# chat : 通用问答/闲聊，不检索
# rag  : 需要查知识库，触发稠密+稀疏检索+图谱
INTENT_LABELS = {"chat", "rag"}

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=BAILIAN_API_KEY, base_url=BAILIAN_BASE_URL)
    return _client


async def detect_intent(user_msg: str) -> str:
    """用百炼 tongyi-intent-detect-v3 做意图分类，返回 chat / rag

    只判断是否需要 RAG 检索。工具调用由 ReAct 自行决策。
    """
    prompt = f"""你是一个意图分类助手。判断用户问题是否需要检索个人知识库。

## 分类规则
- rag：问题涉及用户的个人数据（文档、合同、笔记、联系人、日程、产品、项目），需要检索知识库
- chat：通用知识问答（历史、科学、常识、编程）、闲聊（你好、谢谢）、实时查询（天气、时间、导航）等

## 示例
- "我的合同里有没有违约条款" → rag
- "帮我查一下上周的会议记录" → rag
- "项目管理文档里关于部署流程怎么写的" → rag
- "什么是微服务架构" → chat
- "今天天气怎么样" → chat
- "现在几点了" → chat
- "帮我导航到最近的加油站" → chat
- "你好啊，讲个笑话" → chat
- "成都到北京多远" → chat

用户问题：{user_msg}

## 输出（只输出一个词，不要解释，不要标点）
意图："""

    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=INTENT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10,
        )
        intent = resp.choices[0].message.content.strip().lower()

        if intent in INTENT_LABELS:
            logger.info("意图识别: '%s' → %s", user_msg[:60], intent)
            return intent

        logger.warning("意图识别返回未知类别 '%s'，回退为 chat", intent)
        return "chat"

    except Exception as e:
        logger.warning("意图识别调用失败: %s，回退为 chat", e)
        return "chat"
