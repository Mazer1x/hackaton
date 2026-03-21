# agents/validate_agent/llm/tools/perplexity_tool.py
"""Инструмент веб-поиска: модели Perplexity через OpenRouter (Chat Completions)."""
from __future__ import annotations

import json
import os

import requests
from langchain_core.tools import tool


def _openrouter_headers() -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {(os.getenv('OPENROUTER_API_KEY') or '').strip()}",
        "Content-Type": "application/json",
    }
    referer = (os.getenv("OPENROUTER_HTTP_REFERER") or "").strip()
    if referer:
        headers["HTTP-Referer"] = referer
    title = (os.getenv("OPENROUTER_X_TITLE") or "").strip()
    if title:
        headers["X-Title"] = title
    return headers


def _perplexity_request(user_query: str) -> str:
    api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        return "Ошибка: OPENROUTER_API_KEY не задан в окружении."
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip(
        "/"
    )
    url = f"{base_url}/chat/completions"
    # OpenRouter: perplexity/sonar, perplexity/sonar-pro, perplexity/sonar-reasoning, …
    model = (os.getenv("PERPLEXITY_MODEL") or "perplexity/sonar").strip()
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": user_query}],
    }
    try:
        r = requests.post(
            url, headers=_openrouter_headers(), json=payload, timeout=120
        )
        r.raise_for_status()
        data = r.json()
        choices = data.get("choices") or []
        if not choices:
            return json.dumps(data, ensure_ascii=False)[:8000]
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if content:
            return str(content)
        return json.dumps(data, ensure_ascii=False)[:8000]
    except requests.RequestException as e:
        return f"Ошибка запроса к OpenRouter (Perplexity): {e!s}"


@tool
def perplexity_search(query: str) -> str:
    """Поиск в интернете через Perplexity. Вызывай только если без свежих данных из сети нельзя уверенно править код: документация/версии API, breaking changes, редкая библиотека, неочевидная ошибка сборки. Для смены цвета, отступов, текста, простого Tailwind/Astro — не вызывай."""
    q = (query or "").strip()
    if not q:
        return "Пустой запрос."
    return _perplexity_request(q)


def get_perplexity_search_tools():
    return [perplexity_search]
