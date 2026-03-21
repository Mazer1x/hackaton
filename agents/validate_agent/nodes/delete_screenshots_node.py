"""
Нода: удаляет локальные скриншоты после git_commit_push.
Читает state.screenshot_paths и state.screenshot_dir, удаляет файлы с диска,
очищает screenshot_paths в state.
"""
from pathlib import Path
from typing import Any

from agents.validate_agent.state import ValidateAgentState


def delete_screenshots_node(state: ValidateAgentState) -> dict[str, Any]:
    """
    Удаляет файлы из screenshot_paths, при необходимости — пустую screenshot_dir.
    Возвращает обновление state: screenshot_paths = [], опционально screenshot_message.
    """
    paths = state.get("screenshot_paths") or []
    screenshot_dir = state.get("screenshot_dir")
    deleted = 0
    for p in paths:
        if not p or not isinstance(p, str):
            continue
        path = Path(p)
        if path.is_file():
            try:
                path.unlink(missing_ok=True)
                deleted += 1
            except OSError:
                pass
    if screenshot_dir:
        dir_path = Path(screenshot_dir)
        if dir_path.is_dir() and not any(dir_path.iterdir()):
            try:
                dir_path.rmdir()
            except OSError:
                pass
    msg_suffix = f" Удалено локальных скринов: {deleted}."
    prev_msg = (state.get("screenshot_message") or "").strip()
    return {
        "screenshot_paths": [],
        "screenshot_message": (prev_msg + msg_suffix).strip() if deleted else prev_msg,
    }
