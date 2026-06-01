from __future__ import annotations

from langchain_openai import ChatOpenAI
from tiktoken import encoding_for_model

from ..core.config import CHAT_MODEL, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL

_enc = encoding_for_model("gpt-4")


def count_tokens(messages: list[dict]) -> int:
    total = 0
    for message in messages:
        total += len(_enc.encode(message.get("content", "") or ""))
    return total


def build_llm(temperature: float = 0.7, max_tokens: int = 4096) -> ChatOpenAI:
    return ChatOpenAI(
        model=CHAT_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )
