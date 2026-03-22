"""Prepare state for spec pipeline: guideline bundle json_data → json_data + site_target."""
from __future__ import annotations

import copy
import json
import logging
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agents.generate_agent.spec.utils.llm import get_llm
from agents.generate_agent.spec.utils.site_target import normalize_site_target

log = logging.getLogger(__name__)


class _SiteTargetInfer(BaseModel):
    """Строго mobile | desktop — как в normalize_site_target."""

    site_target: Literal["mobile", "desktop"] = Field(
        description="mobile если ТЗ про телефон/PWA/мобильный первичный сценарий; иначе desktop"
    )


_SITE_TARGET_SYSTEM = """Ты определяешь целевой класс устройств для продукта из ТЗ (user_preferences + business_requirements).

Верни site_target:
- mobile — мобильное приложение, PWA, мобильный банк/финтех, «для смартфона», touch-first, основной сценарий на телефоне.
- desktop — веб для ПК, админка, SaaS в браузере на десктопе, если акцент не на телефоне или не указан.

При неоднозначности или общем лендинге без «мобильного» акцента выбирай desktop."""


async def _infer_site_target_llm(state: dict[str, Any]) -> Literal["mobile", "desktop"]:
    jd = state.get("json_data")
    if not isinstance(jd, dict):
        jd = {}
    prefs = jd.get("user_preferences")
    user_prefs = prefs if isinstance(prefs, dict) else {}
    br = jd.get("business_requirements")
    business_req = br.strip() if isinstance(br, str) else ""
    if not business_req:
        gl = jd.get("guideline")
        if isinstance(gl, str) and gl.strip():
            business_req = gl.strip()[:24000]
    prefs_json = json.dumps(user_prefs, ensure_ascii=False, indent=2) if user_prefs else "{}"
    user = (
        f"USER_PREFERENCES (JSON):\n{prefs_json}\n\n"
        f"BUSINESS_REQUIREMENTS:\n{business_req[:24000]}\n"
    )
    llm = get_llm(tier="concept", temperature=0.15, max_tokens=128)
    messages = [
        SystemMessage(content=_SITE_TARGET_SYSTEM),
        HumanMessage(content=user + "\nВерни JSON site_target: mobile или desktop."),
    ]
    llm_so = llm.with_structured_output(_SiteTargetInfer, method="json_schema")
    try:
        out = await llm_so.ainvoke(messages)
        if out is not None and out.site_target in ("mobile", "desktop"):
            return out.site_target
    except Exception as exc:
        log.warning("infer_site_target: structured failed (%s), fallback desktop", exc)
    return "desktop"


def _explicit_site_target(state: dict[str, Any]) -> Literal["mobile", "desktop"] | None:
    """Только если в инпуте явно задано mobile или desktop."""
    v = _pick_site_target_raw(state)
    if v is None:
        return None
    s = str(v).strip().lower()
    if s == "mobile":
        return "mobile"
    if s == "desktop":
        return "desktop"
    return None


def _pick_site_target_raw(state: dict[str, Any]) -> Any:
    """Resolve site_target from graph input (top-level, json_data, input wrapper)."""
    v = state.get("site_target")
    if v is not None:
        return v
    jd = state.get("json_data")
    if isinstance(jd, dict):
        if jd.get("site_target") is not None:
            return jd.get("site_target")
        prefs = jd.get("user_preferences")
        if isinstance(prefs, dict) and prefs.get("site_target") is not None:
            return prefs.get("site_target")
    inp = state.get("input")
    if isinstance(inp, dict):
        if inp.get("site_target") is not None:
            return inp.get("site_target")
        inj = inp.get("json_data")
        if isinstance(inj, dict) and inj.get("site_target") is not None:
            return inj.get("site_target")
    return None


def _resolve_json_data_dict(state: dict[str, Any]) -> dict[str, Any] | None:
    """Prefer full json_data from state or Studio input wrapper."""
    jd = state.get("json_data")
    if isinstance(jd, dict) and jd:
        return jd
    inp = state.get("input")
    if isinstance(inp, dict):
        inner = inp.get("json_data")
        if isinstance(inner, dict) and inner:
            return inner
    return jd if isinstance(jd, dict) else None


def _is_guideline_bundle(d: dict[str, Any]) -> bool:
    g = d.get("guideline")
    b = d.get("business_requirements")
    if isinstance(g, str) and g.strip():
        return True
    if isinstance(b, str) and b.strip():
        return True
    return False


async def prepare_spec_input(state: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize input: json_data must be a site guideline bundle
    (non-empty guideline and/or business_requirements).

    site_target: если в инпуте явно mobile/desktop — используем; иначе LLM по user_preferences + business_requirements.
    """
    raw = _resolve_json_data_dict(state)
    if not raw:
        raw = {}

    if not _is_guideline_bundle(raw):
        raise ValueError(
            "В json_data нужен формат guideline bundle: непустые поля guideline и/или business_requirements. "
            "Пример: json/site_guideline_bundle.json"
        )

    explicit = _explicit_site_target(state)
    if explicit is not None:
        site_target = explicit
    else:
        site_target = await _infer_site_target_llm({**state, "json_data": raw})

    out = copy.deepcopy(raw)
    out["site_target"] = site_target
    return {"json_data": out, "site_target": site_target}
