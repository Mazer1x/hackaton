"""Multimodal HumanMessage: текст + image_url для vision-моделей (OpenRouter / Gemini)."""
from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage

# Макс. картинок за один запрос (планирование / execute)
MAX_IMAGES_PER_MESSAGE = 16


def merge_bundle_image_urls(jd: dict[str, Any] | None) -> list[str]:
    """
    Уникальные https URL из json_data после flatten:
    guideline_image_urls → business_image_urls → wishes_image_urls.
    """
    if not isinstance(jd, dict):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for key in ("guideline_image_urls", "business_image_urls", "wishes_image_urls"):
        raw = jd.get(key)
        if not isinstance(raw, list):
            continue
        for u in raw:
            if not isinstance(u, str):
                continue
            u = u.strip()
            if not u.startswith("http") or u in seen:
                continue
            seen.add(u)
            out.append(u)
    return out[:MAX_IMAGES_PER_MESSAGE]


def bundle_reference_images_text_block(urls: list[str]) -> str:
    """
    Дублирует URL в текстовой части промпта. Только vision-блоков недостаточно: модель «видит» картинку,
    но часто не переносит точный https в <img src> — ей нужен явный список строк для копирования.
    """
    if not urls:
        return ""
    lines = [
        "",
        "=== USER REFERENCE IMAGES (mandatory in the site) ===",
        "Embed EVERY URL below in real markup (e.g. <img src=\"URL\" alt=\"...\" /> or Astro <Image src=\"URL\" width={...} height={...} />).",
        "Use these exact https strings as src. Do not omit them, do not swap for placeholders or stock photos.",
        "For planning: include sections (Hero / Gallery / Works) that actually display these assets.",
        "",
    ]
    for i, u in enumerate(urls, 1):
        lines.append(f"{i}. {u}")
    lines.append("=== END USER REFERENCE IMAGES ===")
    lines.append("")
    return "\n".join(lines)


def human_message_text_and_images(text: str, image_urls: list[str] | None) -> HumanMessage:
    """Один HumanMessage: текст (с дублированием URL для копирования в код) + image_url блоки."""
    urls = [u.strip() for u in (image_urls or []) if isinstance(u, str) and u.strip().startswith("http")]
    urls = urls[:MAX_IMAGES_PER_MESSAGE]
    if not urls:
        return HumanMessage(content=text)
    full_text = text + bundle_reference_images_text_block(urls)
    parts: list[dict[str, Any]] = [{"type": "text", "text": full_text}]
    for u in urls:
        parts.append({"type": "image_url", "image_url": {"url": u}})
    return HumanMessage(content=parts)
