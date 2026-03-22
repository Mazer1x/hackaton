# nodes/synthesize_guideline_from_screenshots_node.py
"""
Vision: по локальным PNG из screenshot_paths собирает session_export (strategy + design)
для подстановки в prepare_spec_input, если не было готового ТЗ.
"""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agents.generate_agent.llm.chat_factory import get_chat_llm

VISION_MODEL_ENV = "VALIDATE_VISION_MODEL"
DEFAULT_VISION_MODEL = "google/gemini-3-flash-preview"
MAX_IMAGES = 8
MAX_IMAGE_BYTES = 1_400_000

SYSTEM = """Ты — аналитик продуктового дизайна. По скриншотам **уже существующего** сайта восстанови
черновое ТЗ в JSON. Ничего не выдумывай про юридические данные: если на экране нет реквизитов — опусти rkn или поставь заглушки null.

Верни **один** JSON-объект без markdown, со структурой:
{
  "site_target": "desktop" | "mobile",
  "strategy": {
    "brand_name": "строка — с логотипа/шапки или «Неизвестно»",
    "activity": "чем занимается бизнес — по тексту на экране",
    "audience": "кратко",
    "positioning": "кратко",
    "usp": "отличие — если видно",
    "offer": "оффер/призыв — если видно",
    "site_goal": "Продажи" | "Заявки" | "Доверие" | "Презентация",
    "price": "Низкий" | "Средний" | "Высокий" | "Индивидуально",
    "work_hours": "строка или пусто",
    "address": "если есть на сайте",
    "contacts": { "phone": bool, "telegram": bool, "form": bool, "phone_link": "", "telegram_link": "" }
  },
  "design": {
    "style": "описание палитры, настроения, стиля как на скринах",
    "typography": "Минимум текста" | "Средний объём" | "Много текста",
    "animations": "Без анимаций" | "Деликатные" | "Средние" | "Максимум",
    "reviews": "цитаты если видны, иначе пустая строка",
    "faq": "если видно блок FAQ, иначе пустая строка"
  },
  "rkn": null
}

Поля strategy и design должны быть **объектами** с перечисленными ключами (contacts может быть частичным)."""


def _parse_json(raw: str) -> dict[str, Any] | None:
    raw = (raw or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if m:
        raw = m.group(1).strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    obj = re.search(r"\{[\s\S]*\}", raw)
    if obj:
        try:
            data = json.loads(obj.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass
    return None


def _image_blocks(paths: list[str]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for p in paths[:MAX_IMAGES]:
        try:
            raw = Path(p).read_bytes()
        except Exception:
            continue
        if len(raw) > MAX_IMAGE_BYTES:
            raw = raw[:MAX_IMAGE_BYTES]
        b64 = base64.standard_b64encode(raw).decode("ascii")
        blocks.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            }
        )
    return blocks


async def synthesize_guideline_from_screenshots_node(state: dict) -> dict:
    paths = [p for p in (state.get("screenshot_paths") or []) if p]
    if not paths:
        return {
            "guideline_source": "none",
            "guideline_synthesis_error": "Нет screenshot_paths после съёмки.",
        }

    model = os.getenv(VISION_MODEL_ENV) or os.getenv("OPENROUTER_MODEL") or DEFAULT_VISION_MODEL
    llm = get_chat_llm(model=model, temperature=0.25, max_tokens=8192)
    img_blocks = _image_blocks(paths)
    if not img_blocks:
        return {
            "guideline_source": "none",
            "guideline_synthesis_error": "Не удалось прочитать PNG для vision.",
        }

    user_text = (
        f"Скриншотов: {len(img_blocks)} (фрагменты страницы). "
        "Восстанови JSON ТЗ по правилам системного сообщения."
    )
    user_content: list[str | dict] = [{"type": "text", "text": user_text}]
    user_content.extend(img_blocks)
    messages = [
        SystemMessage(content=SYSTEM),
        HumanMessage(content=user_content),
    ]
    try:
        response = await llm.ainvoke(messages)
        raw = getattr(response, "content", None) or ""
        if isinstance(raw, list):
            parts = []
            for b in raw:
                if isinstance(b, dict) and b.get("type") == "text":
                    parts.append(b.get("text", ""))
                else:
                    parts.append(str(b))
            raw = " ".join(parts)
        raw = str(raw)
        parsed = _parse_json(raw)
        if not parsed or not isinstance(parsed.get("strategy"), dict) or not isinstance(
            parsed.get("design"), dict
        ):
            return {
                "guideline_source": "failed",
                "guideline_synthesis_error": "Модель не вернула валидный strategy/design JSON.",
                "guideline_synthesis_raw": raw[:4000],
            }
        site_target = parsed.get("site_target")
        if site_target not in ("mobile", "desktop"):
            site_target = "desktop"
        session_export: dict[str, Any] = {
            "strategy": parsed["strategy"],
            "design": parsed["design"],
            "site_target": site_target,
        }
        if parsed.get("rkn") is not None:
            session_export["rkn"] = parsed["rkn"]
        merged_json = {**session_export}
        return {
            "session_export": session_export,
            "json_data": merged_json,
            "site_target": site_target,
            "guideline_source": "screenshot_synthesis",
            "site_info": f"Guideline синтезирован по {len(img_blocks)} скринам (vision).",
        }
    except Exception as e:
        return {
            "guideline_source": "failed",
            "guideline_synthesis_error": str(e),
        }
