import json
import logging
import re
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from langchain_openai import ChatOpenAI

from ..core.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, CHAT_MODEL
from ..core.prompts import NEWS_BRIEFING_PROMPT
from ..models.news import DailyBriefing
from ..tools import ALL_TOOLS

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 10


def _build_llm(temperature: float = 0.3, max_tokens: int = 4096) -> ChatOpenAI:
    return ChatOpenAI(
        model=CHAT_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )


def _extract_json(text: str) -> dict | None:
    """从 LLM 响应中提取 JSON 对象。"""
    text = text.strip()
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 尝试匹配 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # 尝试匹配 { ... } 对象
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


async def run_news_agent(keywords: list[str], target_date: str) -> dict:
    """非流式 ReAct agent，使用 Linkup MCP 搜索新闻并生成简报。"""
    system_prompt = NEWS_BRIEFING_PROMPT.format(
        keywords=", ".join(keywords),
        target_date=target_date,
    )

    messages = [{"role": "system", "content": system_prompt}]
    tool_map = {t.name: t for t in ALL_TOOLS}
    llm = _build_llm(temperature=0.3, max_tokens=8192).bind_tools(ALL_TOOLS)

    logger.info("新闻 agent 启动, 关键词=%s, 日期=%s, 可用工具=%s",
                keywords, target_date, list(tool_map.keys()))

    for iteration in range(MAX_TOOL_ITERATIONS):
        response = await llm.ainvoke(messages)

        tool_calls = getattr(response, "tool_calls", None) or []
        content = response.content or ""

        messages.append({"role": "assistant", "content": content})

        if not tool_calls:
            logger.info("新闻 agent 完成, 迭代=%d, 无工具调用", iteration + 1)
            break

        tool_results = []
        for tc in tool_calls:
            name = tc.get("name", "")
            args = tc.get("args", {})
            fn = tool_map.get(name)
            if fn:
                try:
                    result = await fn.ainvoke(args)
                    result_str = str(result)
                    logger.debug("工具 %s(%s) → %d 字符", name, args, len(result_str))
                except Exception as e:
                    result_str = f"工具调用失败: {e}"
                    logger.warning("工具 %s 失败: %s", name, e)
            else:
                result_str = f"未知工具: {name}"
                logger.warning("未知工具: %s", name)

            tool_results.append(f"[工具: {name}]\n{result_str}")

        merged = "\n".join(tool_results)
        messages.append({"role": "user", "content": f"工具返回结果:\n{merged}"})

    # 从最终响应中提取 JSON
    result = _extract_json(messages[-1].get("content", ""))
    if result is None:
        # 尝试从倒数第二个消息提取（有时最后一个只是确认语）
        for msg in reversed(messages[:-1]):
            r = _extract_json(msg.get("content", ""))
            if r:
                result = r
                break

    if result is None:
        raise ValueError("无法从 LLM 响应中解析简报 JSON")

    return result


async def generate_briefing(
    user_id: str,
    keywords: list[str],
    target_date: str,
    db: AsyncSession,
) -> DailyBriefing:
    """为指定用户生成指定日期的新闻简报。"""
    # 检查是否已存在
    existing = (await db.execute(
        select(DailyBriefing).where(
            DailyBriefing.user_id == user_id,
            DailyBriefing.date == date.fromisoformat(target_date),
        )
    )).scalar_one_or_none()

    if existing:
        existing.status = "generating"
        existing.error_msg = None
        briefing = existing
    else:
        briefing = DailyBriefing(
            user_id=user_id,
            date=date.fromisoformat(target_date),
            keywords_used=keywords,
            status="generating",
        )
        db.add(briefing)

    await db.commit()

    try:
        data = await run_news_agent(keywords, target_date)
        briefing.title = data.get("title", f"{target_date} 每日新闻简报")
        briefing.news_items = data.get("news_items", [])
        briefing.status = "completed"
        logger.info("简报生成成功: user=%s date=%s items=%d",
                    user_id, target_date, len(briefing.news_items))
    except Exception as e:
        briefing.status = "failed"
        briefing.error_msg = str(e)
        logger.exception("简报生成失败: user=%s date=%s", user_id, target_date)

    briefing.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(briefing)
    return briefing


async def get_user_keywords(user_id: str, db: AsyncSession) -> list[str]:
    from ..models.user import User
    user = await db.get(User, user_id)
    return user.news_keywords or [] if user else []


async def update_user_keywords(
    user_id: str, keywords: list[str], db: AsyncSession
) -> list[str]:
    from ..models.user import User
    user = await db.get(User, user_id)
    if not user:
        raise ValueError("用户不存在")
    user.news_keywords = keywords
    user.updated_at = datetime.utcnow()
    await db.commit()
    return keywords


async def get_briefing_by_date(
    user_id: str, target_date: str, db: AsyncSession
) -> DailyBriefing | None:
    return (await db.execute(
        select(DailyBriefing).where(
            DailyBriefing.user_id == user_id,
            DailyBriefing.date == date.fromisoformat(target_date),
        )
    )).scalar_one_or_none()


async def list_briefings(
    user_id: str, db: AsyncSession
) -> list[DailyBriefing]:
    result = await db.execute(
        select(DailyBriefing)
        .where(DailyBriefing.user_id == user_id)
        .order_by(desc(DailyBriefing.date))
    )
    return list(result.scalars().all())
