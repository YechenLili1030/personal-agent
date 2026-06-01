from __future__ import annotations

import json
import logging
import time
from typing import AsyncGenerator

from ..core.config import CHAT_MODEL
from ..core.prompts import TITLE_PROMPT
from ..tools import ALL_TOOLS
from .chat_common import build_llm, count_tokens

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5


async def run_chat_agent(messages: list[dict]) -> AsyncGenerator[str, None]:
    tool_map = {tool.name: tool for tool in ALL_TOOLS}
    llm = build_llm().bind_tools(ALL_TOOLS)
    started_at = time.time()
    total_input = 0
    total_output = 0

    for iteration in range(MAX_TOOL_ITERATIONS):
        collected_content = ""
        tool_calls: list[dict] = []

        for chunk in llm.stream([(message["role"], message["content"]) for message in messages]):
            if chunk.content:
                collected_content += chunk.content
                yield chunk.content

            if chunk.tool_call_chunks:
                _append_tool_call_chunks(tool_calls, chunk.tool_call_chunks)

        total_input += count_tokens(messages)
        total_output += count_tokens([{"role": "assistant", "content": collected_content}])

        if not tool_calls:
            break

        tool_results = await _invoke_tools(tool_calls, tool_map)
        messages.append({"role": "assistant", "content": collected_content or " "})

        if not tool_results:
            break
        messages.append({"role": "user", "content": "工具返回结果:\n" + "\n\n".join(tool_results)})

    elapsed = (time.time() - started_at) * 1000
    total = total_input + total_output
    logger.info(
        "调用完成 | model=%s | rounds=%d | input=%dt output=%dt total=%dt | %.0fms",
        CHAT_MODEL,
        iteration + 1,
        total_input,
        total_output,
        total,
        elapsed,
    )


def _append_tool_call_chunks(tool_calls: list[dict], chunks: list[dict]) -> None:
    for chunk in chunks:
        index = chunk.get("index", 0)
        while len(tool_calls) <= index:
            tool_calls.append({"name": "", "args": ""})
        if chunk.get("name"):
            tool_calls[index]["name"] += chunk["name"]
        if chunk.get("args"):
            tool_calls[index]["args"] += chunk["args"]


async def _invoke_tools(tool_calls: list[dict], tool_map: dict) -> list[str]:
    results = []
    for tool_call in tool_calls:
        name = tool_call["name"].strip()
        tool = tool_map.get(name)
        if not tool:
            logger.warning("未知工具: %s", name)
            continue

        try:
            args = json.loads(tool_call["args"]) if tool_call["args"].strip() else {}
            result = await tool.ainvoke(args)
            results.append(f"[工具: {name}]\n{result}")
            logger.info("工具调用: %s(%s) -> %s", name, args, str(result)[:120])
        except Exception as exc:
            logger.error("工具执行失败 %s: %s", name, exc)
            results.append(f"[工具: {name}]\n执行失败: {exc}")

    return results


async def generate_title(user_msg: str) -> str:
    started_at = time.time()
    try:
        llm = build_llm(temperature=0.3, max_tokens=30)
        response = llm.invoke(TITLE_PROMPT.format(text=user_msg))
        title = response.content.strip()
        elapsed = (time.time() - started_at) * 1000
        logger.info("标题生成 | %s | %.0fms", title, elapsed)
        return title
    except Exception as exc:
        logger.warning("标题生成失败: %s", exc)
        return user_msg[:20]
