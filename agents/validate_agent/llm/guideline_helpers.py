# agents/validate_agent/llm/guideline_helpers.py
"""Проверка наличия guideline (ТЗ) в state для обхода синтеза со скринов."""
from __future__ import annotations

from typing import Any


def _strategy_design_ok(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    s = obj.get("strategy")
    d = obj.get("design")
    return isinstance(s, dict) and s and isinstance(d, dict) and d


def has_guideline(state: dict[str, Any]) -> bool:
    """
    True, если уже есть session_export или json_data с непустыми strategy и design
    (как ожидает prepare_spec_input / semantic_parser).
    """
    se = state.get("session_export")
    if _strategy_design_ok(se):
        return True
    jd = state.get("json_data")
    if _strategy_design_ok(jd):
        return True
    inp = state.get("input")
    if isinstance(inp, dict):
        jd2 = inp.get("json_data") or inp.get("session_export")
        if _strategy_design_ok(jd2):
            return True
    return False
