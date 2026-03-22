"""
Нода: визуальная проверка скриншотов через vision (режим «правки», не аудит ТЗ).
Для каждой страницы — отдельный запрос; смотрим, выполнен ли запрос пользователя (цвет кнопки и т.д.).
Итог по-прежнему в validation_result (valid / errors / warnings) для совместимости с графом fix.
"""
import json
import os
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agents.generate_agent.llm.chat_factory import get_chat_llm
from agents.validate_agent.state import ValidateAgentState
from agents.validate_agent.nodes.should_fix_or_edit_site import last_human_text
from agents.validate_agent.utils.screenshot_groups import (
    page_batches_for_vision,
    resolve_page_id_for_screenshot_group,
)

# Модель с поддержкой зрения. Задаётся в .env: VALIDATE_VISION_MODEL (иначе OPENROUTER_MODEL, иначе дефолт).
VISION_MODEL_ENV = "VALIDATE_VISION_MODEL"
DEFAULT_VISION_MODEL = "openai/gpt-4o-mini"

SYSTEM_PROMPT_PAGE = """Ты — эксперт по вёрстке и UX. Тебе прислали скриншоты **одной страницы** сайта: кадры по скроллу сверху вниз (один столбец).
Если в запросе есть контекст ТЗ (бренд, стиль, содержание) — сверь эту страницу с ним: соответствует ли блокам и стилю.
Проанализируй визуально только эту страницу:
- читаемость текста, контраст, шрифты;
- структура и логика блоков;
- общее впечатление (профессионально/сыро/сломанная вёрстка);
- явные баги: обрезанный контент, наложения, пустые области, сломанные отступы.

Ответь строго одним JSON-объектом без markdown-обёртки и без комментариев:
{
  "valid": true или false,
  "errors": ["список критичных проблем"],
  "warnings": ["список замечаний"],
  "summary": "краткое резюме по этой странице (1–3 предложения)"
}
Если ошибок нет — errors: []. Поле summary обязательно."""

USER_TEXT_TEMPLATE_PAGE = """Страница (метка): {page_label}.
Кадров по скроллу на этой странице: {count}.
Оцени только эту страницу и верни JSON: valid, errors, warnings, summary."""


def _build_context_from_state(state: ValidateAgentState) -> str:
    """Контекст для vision: запрос пользователя + кратко json_data / site_info."""
    parts: list[str] = []
    user_ask = last_human_text(state)
    if user_ask:
        parts.append(f"Запрос пользователя (что должно быть отражено на скринах после правок): {user_ask}")
    site_info = state.get("site_info")
    if site_info:
        parts.append(f"Краткий контекст сайта: {site_info}")
    json_data = state.get("json_data") or {}
    if json_data:
        strategy = json_data.get("strategy") or {}
        design = json_data.get("design") or {}
        if strategy:
            parts.append(f"Бренд/оффер: {strategy.get('brand_name', '')} — {strategy.get('offer', '')}")
            if strategy.get("activity"):
                parts.append(f"Активность: {strategy['activity']}")
        if design:
            if design.get("style"):
                parts.append(f"Ожидаемый стиль: {design['style']}")
            if design.get("typography"):
                parts.append(f"Типографика: {design['typography']}")
        gh = json_data.get("guideline")
        if isinstance(gh, str) and gh.strip():
            t = gh.strip()
            cap = 4000
            parts.append(
                f"Гайдлайн (стиль/контент): {t[:cap]}{'…' if len(t) > cap else ''}"
            )
        br = json_data.get("business_requirements")
        if isinstance(br, str) and br.strip():
            t = br.strip()
            cap = 2000
            parts.append(
                f"Требования / ТЗ (фрагмент): {t[:cap]}{'…' if len(t) > cap else ''}"
            )
    project_spec = state.get("project_spec") or {}
    if project_spec:
        brief = project_spec.get("content_brief") or project_spec.get("short_summary")
        if brief:
            parts.append(f"Содержание: {brief}")
    if not parts:
        return ""
    return "\n\nКонтекст для проверки скринов:\n" + "\n".join(f"- {p}" for p in parts)


def _mandatory_design_tokens_block(state: ValidateAgentState) -> str:
    """Всегда непустая строка для промпта: JSON или явное указание, что токены не заданы."""
    dt = state.get("design_tokens") or {}
    if isinstance(dt, dict) and dt:
        raw = json.dumps(dt, ensure_ascii=False, indent=2)
        cap = 3500
        return raw[:cap] + ("…" if len(raw) > cap else "")
    return (
        "[design_tokens в state отсутствуют или пусты — проверь согласованность по брифу страницы; "
        "если на скрине видна палитра, не противоречит ли она описанию в page_brief.]"
    )


def _build_context_for_page(state: ValidateAgentState, page_label: str) -> str:
    """
    Для каждой группы скринов — свой контекст: page_brief[page_id], если есть маппинг метки → page_id.
    Иначе — общий контекст (как раньше).
    """
    pb = state.get("page_briefs")
    pid = resolve_page_id_for_screenshot_group(
        page_label,
        pb if isinstance(pb, dict) else None,
    )
    if pid and isinstance(pb, dict) and pid in pb:
        parts: list[str] = []
        user_ask = last_human_text(state)
        if user_ask:
            parts.append(f"Запрос пользователя: {user_ask}")
        brief_json = json.dumps(pb[pid], ensure_ascii=False, indent=2)
        parts.append(
            f"Эталон для этой страницы (page_brief «{pid}»). Сверь скриншоты с брифом — секции, контент-фокус, "
            f"компоненты, design_notes, навигация.\n{brief_json}"
        )
        parts.append(
            "Общие design_tokens (обязательно: палитра и типографика на весь сайт; сверь скрин с этими токенами "
            "и с брифом страницы):\n"
            + _mandatory_design_tokens_block(state)
        )
        return "\n\nКонтекст для проверки скринов:\n" + "\n\n".join(parts)
    return _build_context_from_state(state)


def _build_user_content_page(
    screenshot_urls: list[str],
    context: str,
    page_label: str,
) -> list[dict]:
    """Текст + image_url блоки для одной страницы."""
    text = USER_TEXT_TEMPLATE_PAGE.format(page_label=page_label, count=len(screenshot_urls))
    if context:
        text = context + "\n\n" + text
    blocks: list[dict] = [{"type": "text", "text": text}]
    for url in screenshot_urls:
        if url and isinstance(url, str) and url.startswith("http"):
            blocks.append({
                "type": "image_url",
                "image_url": {"url": url},
            })
    return blocks


def _parse_validation_json(raw: str) -> dict[str, Any] | None:
    """Достаёт JSON из ответа (игнорирует markdown и мусор вокруг)."""
    raw = (raw or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if m:
        raw = m.group(1).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    obj_match = re.search(r"\{[\s\S]*\}", raw)
    if obj_match:
        try:
            data = json.loads(obj_match.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return None


def _plain_text_to_result(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()[:1500]
    return {
        "valid": False,
        "errors": ["Модель вернула текст вместо JSON. Ответ сохранён в summary."],
        "warnings": [],
        "summary": text or "Пустой ответ модели.",
    }


def _merge_page_results(
    page_label: str,
    parsed: dict[str, Any] | None,
    raw: str,
) -> dict[str, Any]:
    if not parsed:
        pt = _plain_text_to_result(raw)
        return {
            "page": page_label,
            "valid": pt["valid"],
            "errors": pt["errors"],
            "warnings": pt["warnings"],
            "summary": pt["summary"],
        }
    return {
        "page": page_label,
        "valid": bool(parsed.get("valid", False)),
        "errors": parsed.get("errors") if isinstance(parsed.get("errors"), list) else [],
        "warnings": parsed.get("warnings") if isinstance(parsed.get("warnings"), list) else [],
        "summary": str(parsed.get("summary", "") or "").strip() or "Без резюме.",
    }


def _aggregate_validation(per_page: list[dict[str, Any]]) -> dict[str, Any]:
    all_valid = all(p.get("valid") for p in per_page)
    merged_errors: list[str] = []
    merged_warnings: list[str] = []
    summary_parts: list[str] = []
    for p in per_page:
        label = str(p.get("page", "?"))
        for e in p.get("errors") or []:
            merged_errors.append(f"[{label}] {e}")
        for w in p.get("warnings") or []:
            merged_warnings.append(f"[{label}] {w}")
        s = str(p.get("summary", "") or "").strip()
        if s:
            summary_parts.append(f"{label}: {s}")
    return {
        "valid": all_valid,
        "errors": merged_errors,
        "warnings": merged_warnings,
        "summary": " · ".join(summary_parts) if summary_parts else "Без резюме.",
        "per_page": per_page,
    }


async def _analyze_screenshots_node(state: ValidateAgentState) -> dict[str, Any]:
    """
    По каждой странице — отдельный vision-запрос; итог объединяется с per_page.
    """
    screenshot_urls = state.get("screenshot_urls") or []
    if not screenshot_urls:
        msg = (state.get("screenshot_message") or "") + " Нет ссылок на скриншоты для анализа."
        return {
            "screenshot_message": msg.strip(),
            "validation_result": {
                "valid": False,
                "errors": ["analyze_screenshots: нет screenshot_urls в state"],
                "warnings": [],
                "summary": "Скриншоты не были загружены или ссылки отсутствуют.",
            },
        }

    batches = page_batches_for_vision(state)
    if not batches:
        msg = (state.get("screenshot_message") or "") + " Не удалось сгруппировать скрины по страницам."
        return {
            "screenshot_message": msg.strip(),
            "validation_result": {
                "valid": False,
                "errors": ["analyze_screenshots: пустые батчи для vision"],
                "warnings": [],
                "summary": "Нет групп страниц для анализа.",
            },
        }

    model = os.getenv(VISION_MODEL_ENV) or os.getenv("OPENROUTER_MODEL") or DEFAULT_VISION_MODEL
    llm = get_chat_llm(model=model, temperature=0.2, max_tokens=2000)

    per_page: list[dict[str, Any]] = []

    for page_label, batch_urls in batches:
        context = _build_context_for_page(state, page_label)
        if not batch_urls:
            per_page.append({
                "page": page_label,
                "valid": False,
                "errors": ["Нет загруженных URL для этой страницы."],
                "warnings": [],
                "summary": "Пропуск: пустой батч.",
            })
            continue

        user_content = _build_user_content_page(batch_urls, context, page_label)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT_PAGE),
            HumanMessage(content=user_content),
        ]
        try:
            response = await llm.ainvoke(messages)
            raw = getattr(response, "content", None) or ""
            if isinstance(raw, list):
                parts = [(b.get("text", "") if isinstance(b, dict) else str(b)) for b in raw]
                raw = " ".join(parts)
            raw = str(raw)
            parsed = _parse_validation_json(raw)
            per_page.append(_merge_page_results(page_label, parsed, raw))
        except Exception as e:
            per_page.append({
                "page": page_label,
                "valid": False,
                "errors": [f"Ошибка vision: {e!s}"],
                "warnings": [],
                "summary": str(e),
            })

    validation_result = _aggregate_validation(per_page)

    n = len(batches)
    msg = state.get("screenshot_message") or ""
    short = validation_result["summary"][:220]
    msg = (msg + f" Проверка правок по скринам ({n} стр.): {short}").strip()
    if len(validation_result["summary"]) > 220:
        msg = msg + "..."

    return {
        "screenshot_message": msg,
        "validation_result": validation_result,
    }
