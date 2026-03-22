# nodes/upload_screenshots_node.py
"""
Нода: загружает скриншоты из state.screenshot_paths на API (POST multipart),
собирает возвращённые URL и пишет их в state.screenshot_urls.
API: POST http://127.0.0.1:5051/api/screenshots с полем file=@path.
Ответ: URL скриншота (например https://media.automatoria.ru/screenshots/74e65b4d88b14be0a207d9e98abf38cd).
"""
import asyncio
import json
import os
from pathlib import Path

from agents.validate_agent.state import ValidateAgentState
from agents.validate_agent.utils.screenshot_groups import group_screenshot_paths_by_page

# Ответ API — публичные URL (например media.automatoria.ru)
UPLOAD_SCREENSHOTS_URL = os.getenv(
    "SCREENSHOT_UPLOAD_URL",
    "http://127.0.0.1:5051/api/screenshots",
)


def _upload_one(path: str) -> tuple[str | None, str | None]:
    """Синхронно загружает один файл.

    Возвращает (url, error): url при успехе или None и текст ошибки при неудаче.
    """
    try:
        import requests
    except ImportError as e:
        return None, f"requests import error: {e!s}"
    p = Path(path)
    if not p.is_file():
        return None, f"file not found: {p}"
    try:
        with open(p, "rb") as f:
            r = requests.post(
                UPLOAD_SCREENSHOTS_URL,
                files={"file": (p.name, f, "image/png")},
                timeout=30,
            )
    except Exception as e:
        return None, f"request error for {p.name}: {e!s}"
    if r.status_code != 200:
        body = (r.text or "").strip()
        snippet = body[:200]
        return None, f"HTTP {r.status_code} for {p.name}: {snippet}"
    text = (r.text or "").strip()
    if not text:
        return None, "empty response body"
    # Ответ может быть:
    # - {"url": "..."}
    # - {"data": {"url": "..."}, "success": true}
    # - просто строка URL
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            if "url" in data and isinstance(data["url"], str):
                return data["url"], None
            if "data" in data and isinstance(data["data"], dict):
                inner = data["data"]
                if "url" in inner and isinstance(inner["url"], str):
                    return inner["url"], None
        if isinstance(data, str) and data.startswith("http"):
            return data, None
    except json.JSONDecodeError:
        # не JSON — пробуем трактовать как прямой URL
        if text.startswith("http"):
            return text, None
        return None, f"invalid JSON/URL: {text[:200]}"
    if text.startswith("http"):
        return text, None
    return None, f"unrecognized response: {text[:200]}"


async def _upload_screenshots_node(state: ValidateAgentState) -> dict:
    """
    Для каждого пути из state.screenshot_paths делает POST на API,
    собирает URL в список и возвращает {"screenshot_urls": [...]}.
    """
    paths = state.get("screenshot_paths") or []
    if not paths:
        return {
            "screenshot_urls": [],
            "screenshot_page_urls": [],
            "screenshot_message": (state.get("screenshot_message") or "")
            + " Нет файлов для загрузки.",
        }

    def _run_uploads() -> tuple[list[str], list[list[str]], list[str]]:
        flat: list[str] = []
        page_urls: list[list[str]] = []
        errors: list[str] = []
        for _, group_paths in group_screenshot_paths_by_page(paths):
            batch: list[str] = []
            for path in group_paths:
                url, err = _upload_one(path)
                if url:
                    batch.append(url)
                    flat.append(url)
                elif err:
                    errors.append(err)
            page_urls.append(batch)
        return flat, page_urls, errors

    urls, screenshot_page_urls, errors = await asyncio.to_thread(_run_uploads)
    msg = state.get("screenshot_message") or ""
    if urls:
        msg = (msg + f" Загружено на сервер: {len(urls)} шт.").strip()
    if errors and not urls:
        # Если вообще ничего не загрузилось — показываем первую детализированную ошибку
        msg = (msg + f" Загрузка на сервер не удалась: {errors[0]}").strip()
    elif errors:
        # Частичный успех: добавим информацию, что были и ошибки
        msg = (msg + f" (часть файлов не загрузилась: {errors[0]})").strip()

    return {
        "screenshot_urls": urls,
        "screenshot_page_urls": screenshot_page_urls,
        "screenshot_message": msg,
    }
