"""查询改写 — 结合近几轮对话历史，用 DeepSeek 将省略/指代问题改写为独立查询"""

from __future__ import annotations
import logging
import time

from openai import OpenAI

from ..core.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL
from ..core.prompts import QUERY_REWRITE_PROMPT

logger = logging.getLogger(__name__)


class DeepSeekQueryRewriter:
    """使用 deepseek-v4-flash 改写查询，禁用 thinking 保证时效"""

    def __init__(self, model: str = "deepseek-v4-flash",
                 history_rounds: int = 5):
        self.model = model
        self.history_rounds = history_rounds
        self._client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )

    @property
    def name(self) -> str:
        return "DeepSeekQueryRewriter"

    async def rewrite(self, query: str, history: list[dict] | None = None) -> str:
        """返回改写后的查询；无需改写时返回原 query"""
        if not history:
            return query

        recent = history[-self.history_rounds * 2:]  # 每轮含 user + assistant
        if not recent:
            return query

        lines = []
        for m in recent:
            role = "用户" if m.get("role") == "user" else "助手"
            content = m.get("content", "")
            if len(content) > 200:
                content = content[:200] + "..."
            lines.append(f"{role}: {content}")

        prompt = QUERY_REWRITE_PROMPT.format(
            history="\n".join(lines),
            question=query,
        )

        t0 = time.time()
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
                extra_body={"thinking": {"type": "disabled"}},
            )
            rewritten = (resp.choices[0].message.content or "").strip()
            elapsed = (time.time() - t0) * 1000
            if rewritten and rewritten != query:
                logger.info("查询改写: '%s' → '%s' | %.0fms", query[:60], rewritten[:80], elapsed)
                return rewritten
            logger.info("查询无需改写: '%s' | %.0fms", query[:60], elapsed)
            return query
        except Exception as e:
            logger.warning("查询改写失败: %s | %.0fms, 回退原查询", e, (time.time() - t0) * 1000)
            return query
