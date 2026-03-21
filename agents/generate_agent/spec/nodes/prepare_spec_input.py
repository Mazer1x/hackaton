"""Prepare state for spec pipeline: map json_data -> session_export for llm_design_requirements."""
from __future__ import annotations

from typing import Any

from agents.generate_agent.spec.utils.site_target import normalize_site_target


def _pick_site_target_raw(state: dict[str, Any], session_export: dict[str, Any] | None) -> Any:
    """Resolve site_target from graph input (top-level, json_data, input wrapper, session_export)."""
    v = state.get("site_target")
    if v is not None:
        return v
    if isinstance(session_export, dict) and session_export.get("site_target") is not None:
        return session_export.get("site_target")
    jd = state.get("json_data")
    if isinstance(jd, dict) and jd.get("site_target") is not None:
        return jd.get("site_target")
    inp = state.get("input")
    if isinstance(inp, dict):
        if inp.get("site_target") is not None:
            return inp.get("site_target")
        inj = inp.get("json_data")
        if isinstance(inj, dict) and inj.get("site_target") is not None:
            return inj.get("site_target")
    return None


def _extract_session_export(state: dict[str, Any]) -> dict[str, Any] | None:
    """Get SessionExport dict from state. Supports: json_data, session_export, input.json_data, input (as export), top-level strategy+design."""
    raw = state.get("json_data") or state.get("session_export")
    # Обёртка типа { "input": { "messages": ..., "json_data": ... } } (LangGraph Studio)
    if (not raw or not isinstance(raw, dict) or "strategy" not in raw) and "input" in state:
        inp = state.get("input")
        if isinstance(inp, dict):
            raw = inp.get("json_data") or inp.get("session_export") or (inp if ("strategy" in inp and "design" in inp) else None)
    if isinstance(raw, dict) and "session_export" in raw and "strategy" not in raw:
        raw = raw.get("session_export", raw)
    if isinstance(raw, dict) and ("strategy" in raw or "design" in raw):
        return raw
    # strategy/design на верхнем уровне state (если вставили только содержимое json_data)
    if isinstance(state.get("strategy"), dict) and isinstance(state.get("design"), dict):
        out = {"strategy": state["strategy"], "design": state["design"]}
        if state.get("rkn") is not None:
            out["rkn"] = state["rkn"]
        return out
    return None


async def prepare_spec_input(state: dict[str, Any]) -> dict[str, Any]:
    """Set session_export from json_data so the spec pipeline can read it. Normalizes site_target (mobile|desktop)."""
    session_export = _extract_session_export(state)
    if not session_export or "strategy" not in session_export:
        raise ValueError(
            "В initial state нет json_data с полями strategy и design. "
            "В поле Input вставьте JSON с ключом json_data, внутри — strategy и design. "
            "Пример: agents/generate_agent/spec/langgraph_input_example.json"
        )
    st_raw = _pick_site_target_raw(state, session_export)
    site_target = normalize_site_target(st_raw)
    merged = {**session_export, "site_target": site_target}
    return {"session_export": merged, "site_target": site_target}
