# nodes/should_fix_or_edit_site.py
"""
После analyze_screenshots: идти в fix_site_react если есть project_path и
(ошибки/предупреждения vision) ИЛИ пользователь явно просит правку в чате (цвет кнопки и т.д.).
"""
from __future__ import annotations

from langchain_core.messages import BaseMessage, HumanMessage


def _human_message_text(m: BaseMessage | dict) -> str:
    if isinstance(m, HumanMessage):
        c = m.content
        return str(c).strip() if c is not None else ""
    if isinstance(m, dict):
        if m.get("type") == "human" or m.get("role") == "user":
            return str(m.get("content", "")).strip()
    return ""


def last_human_text(state: dict) -> str:
    """Текст последнего human-сообщения (Studio / LangChain)."""
    messages = state.get("messages") or []
    for m in reversed(messages):
        t = _human_message_text(m)
        if t:
            return t
    inp = state.get("input")
    if isinstance(inp, dict):
        msgs = inp.get("messages")
        if isinstance(msgs, list):
            for m in reversed(msgs):
                t = _human_message_text(m)  # type: ignore[arg-type]
                if t:
                    return t
    return ""


def user_requests_code_edit(state: dict) -> bool:
    """Эвристика: пользователь просит изменить вёрстку/стили/код."""
    text = last_human_text(state).lower()
    if not text:
        return False
    keywords = (
        "смен",
        "поменя",
        "измени",
        "исправ",
        "сделай",
        "добав",
        "убери",
        "удали",
        "перекрас",
        "покрас",
        "цвет",
        "кнопк",
        "стил",
        "фон",
        "шрифт",
        "отступ",
        "размер",
        "логотип",
        "иконк",
        "хедер",
        "футер",
        "меню",
        "баннер",
        "картинк",
        "изображен",
        "tailwind",
        "css",
        "astro",
        "компонент",
    )
    return any(k in text for k in keywords)


def should_fix_or_edit_site(state: dict) -> str:
    """
    Возвращает имя следующей ноды: fix_site_react или end (ключ end для END в LangGraph).
    """
    project_path = (state.get("project_path") or "").strip()
    if not project_path:
        return "end"
    vr = state.get("validation_result") or {}
    errors = vr.get("errors") or []
    warnings = vr.get("warnings") or []
    if errors or warnings:
        return "fix_site_react"
    if user_requests_code_edit(state):
        return "fix_site_react"
    return "end"
