"""
Сводит вход к виду ValidateAgentState: поля из «bundle» на корне state попадают в json_data.

Файлы вроде json/site_guideline_bundle.json задают business_requirements / guideline /
user_preferences на верхнем уровне; нода копирует их в json_data, если там пусто.
"""
from __future__ import annotations

from typing import Any

from agents.generate_agent.spec.utils.json_data_bundle_v1 import normalize_json_data


def _pick(state: dict, key: str) -> Any:
    v = state.get(key)
    if v is not None and v != "":
        return v
    inp = state.get("input")
    if isinstance(inp, dict):
        v = inp.get(key)
        if v is not None and v != "":
            return v
    return None


def _is_empty(val: Any) -> bool:
    if val is None:
        return True
    if val == "":
        return True
    if isinstance(val, dict) and len(val) == 0:
        return True
    return False


_BUNDLE_KEYS = (
    "business_requirements",
    "guideline",
    "user_preferences",
    "design_preferences",
    "design_reference_url",
)


async def normalize_validate_input_node(state: dict) -> dict:
    jd_raw = _pick(state, "json_data")
    jd: dict[str, Any] = dict(jd_raw) if isinstance(jd_raw, dict) else {}

    updates: dict[str, Any] = {}
    for key in _BUNDLE_KEYS:
        root_val = _pick(state, key)
        if root_val is None:
            continue
        if key not in jd or _is_empty(jd.get(key)):
            jd[key] = root_val

    if jd:
        jd, _changed = normalize_json_data(jd)
        updates["json_data"] = jd

    st = _pick(state, "site_target") or (jd.get("site_target") if jd else None)
    if isinstance(st, str) and st.strip():
        updates["site_target"] = st.strip()

    pb = _pick(state, "page_briefs")
    if isinstance(pb, dict) and pb:
        updates["page_briefs"] = pb

    return updates
