# nodes/should_fix_site.py
"""Условие: после analyze_screenshots идти в fix_site_react, если есть ошибки и задан project_path."""


def should_fix_site(state: dict) -> str:
    validation_result = state.get("validation_result") or {}
    project_path = (state.get("project_path") or "").strip()
    errors = validation_result.get("errors") or []
    if project_path and errors:
        return "fix_site_react"
    return "end"
