from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from ..core.config import (
    BAILIAN_API_KEY,
    BAILIAN_BASE_URL,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    MULTIMODAL_MODEL,
    SUMMARY_MAX_CHARS,
    SUMMARY_MODEL,
)
from ..core.prompts import MULTIMODAL_PROMPT, SUMMARY_PROMPT
from .file_parser import encode_image_base64, encode_pdf_pages_as_images, get_image_mime

logger = logging.getLogger(__name__)


def build_llm(
    model: str,
    temperature: float = 0.3,
    max_tokens: int = 200,
    api_key: str = BAILIAN_API_KEY,
    base_url: str = BAILIAN_BASE_URL,
) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
        base_url=base_url,
    )


async def parse_with_multimodal(file_path: str, file_type: str, filename: str) -> str:
    llm = build_llm(MULTIMODAL_MODEL, max_tokens=2000)

    if file_type == "pdf":
        page_images = encode_pdf_pages_as_images(file_path)
        if not page_images:
            raise ValueError("PDF 页面渲染失败")

        page_texts = []
        for index, image_b64 in enumerate(page_images):
            message = HumanMessage(content=[
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                {"type": "text", "text": f"这是文档《{filename}》的第 {index + 1} 页。{MULTIMODAL_PROMPT}"},
            ])
            response = llm.invoke([message])
            if response.content:
                page_texts.append(response.content.strip())
        return "\n\n".join(page_texts)

    image_b64 = encode_image_base64(file_path)
    mime = get_image_mime(file_path)
    message = HumanMessage(content=[
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
        {"type": "text", "text": f"图片文件名: {filename}\n{MULTIMODAL_PROMPT}"},
    ])
    response = llm.invoke([message])
    return response.content.strip()


async def summarize_document(text: str, filename: str) -> str:
    snippet = text[:SUMMARY_MAX_CHARS]
    prompt = SUMMARY_PROMPT.format(text=snippet)
    try:
        llm = build_llm(
            SUMMARY_MODEL,
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )
        response = llm.invoke(prompt)
        summary = response.content.strip()
        logger.info("文档 %s 摘要: %s", filename, summary)
        return summary
    except Exception as exc:
        logger.warning("文档摘要失败 %s: %s", filename, exc)
        return f"文档: {filename}"
