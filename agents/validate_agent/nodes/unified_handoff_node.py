"""
Между подграфом generate и validate: сброс полей скринов/результата проверки,
чтобы деплой и съём скринов начинались с чистого state (без артефактов прошлых прогонов).

page_briefs, design_tokens, json_data, generation_plan, project_path, repo_name и т.д. не трогаем —
они передаются из generate в validate как есть.
"""
from __future__ import annotations


async def unified_handoff_to_validate_node(state: dict) -> dict:
    return {
        "screenshot_dir": None,
        "screenshot_paths": [],
        "screenshot_urls": [],
        "screenshot_page_urls": None,
        "screenshot_message": None,
        "validation_result": None,
        "fix_attempts": 0,
    }
