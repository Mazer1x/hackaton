"""
Из guideline + json_data.design_preferences LLM извлекает design_tokens (палитра, настроение).
Если в тексте нет визуальных преференсов — не заполняет state; тогда сработает reference-сайт (если есть URL).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field

from agents.generate_agent.spec.utils.json_extract import extract_json
from agents.generate_agent.spec.utils.json_data_bundle_v1 import normalize_json_data
from agents.generate_agent.spec.utils.llm_image_attachment import (
    merge_bundle_image_urls,
    human_message_text_and_images,
)
from agents.generate_agent.spec.utils.llm import get_llm

log = logging.getLogger(__name__)

USER_DESIGN_SYSTEM = """Ты — дизайн-стратег. По тексту guideline, отдельному полю design_preferences и фрагменту ТЗ
реши: задаёт ли пользователь **конкретный визуальный** замысел (цвета, светлая/тёмная тема, типографика, стиль UI).

- Если да — собери **design_tokens** в том же духе, что ниже (реалистичные hex, если названы цвета — переведи в hex).
- Если в текстах только продукт/контент/функции **без** визуального направления — has_user_design_intent: false, design_tokens: null.

Не выдумывай палитру «с нуля», если пользователь её не описал."""


class DesignTokensPayload(BaseModel):
    """Совместимо с reference vision / execute."""

    palette: dict[str, Any] = Field(default_factory=dict)
    bold_design_move: str = ""
    motion: dict[str, Any] = Field(default_factory=dict)
    typography_hint: str = ""


class UserDesignExtractResult(BaseModel):
    has_user_design_intent: bool = False
    design_tokens: Optional[DesignTokensPayload] = None


def _design_preferences_raw(jd: dict) -> str:
    s = jd.get("design_preferences")
    if isinstance(s, str) and s.strip():
        return s.strip()
    prefs = jd.get("user_preferences")
    if isinstance(prefs, dict):
        s2 = prefs.get("design_preferences")
        if isinstance(s2, str) and s2.strip():
            return s2.strip()
    return ""


async def extract_user_design_preferences_node(state: dict[str, Any]) -> dict[str, Any]:
    jd_raw = state.get("json_data")
    jd = jd_raw if isinstance(jd_raw, dict) else {}
    nj, v1_flattened = normalize_json_data(jd)
    base_out: dict[str, Any] = {}
    if v1_flattened:
        base_out["json_data"] = nj
    jd = nj

    if jd.get("explicit_design") is True:
        return base_out

    if _has_palette_from_state(state):
        return base_out

    guideline = (jd.get("guideline") or "").strip() if isinstance(jd.get("guideline"), str) else ""
    br = (jd.get("business_requirements") or "").strip() if isinstance(jd.get("business_requirements"), str) else ""
    dp = _design_preferences_raw(jd)

    if not guideline and not br and not dp:
        return base_out

    bundle = (
        f"DESIGN_PREFERENCES (отдельное поле пользователя):\n{dp or '(пусто)'}\n\n"
        f"GUIDELINE:\n{guideline[:10000]}\n\n"
        f"BUSINESS_REQUIREMENTS (фрагмент):\n{br[:8000]}\n"
    )
    bundle += "\nВерни JSON по схеме: has_user_design_intent, design_tokens (или null)."
    imgs = merge_bundle_image_urls(jd)
    human = human_message_text_and_images(bundle, imgs)
    llm = get_llm(tier="concept", temperature=0.2, max_tokens=2048)
    messages = [SystemMessage(content=USER_DESIGN_SYSTEM), human]
    llm_so = llm.with_structured_output(UserDesignExtractResult, method="json_schema")
    try:
        out = await llm_so.ainvoke(messages)
    except Exception as exc:
        log.warning("extract_user_design: structured failed (%s), fallback", exc)
        out = await _fallback_parse(llm, messages)

    if out is None or not out.has_user_design_intent or out.design_tokens is None:
        return base_out

    pl = out.design_tokens.palette if isinstance(out.design_tokens.palette, dict) else {}
    if not pl:
        return base_out

    tokens: dict[str, Any] = {
        "palette": pl,
        "bold_design_move": out.design_tokens.bold_design_move or "",
        "motion": out.design_tokens.motion if isinstance(out.design_tokens.motion, dict) else {},
        "typography_hint": out.design_tokens.typography_hint or "",
        "source": "user_guideline",
    }
    note = "Design tokens из guideline / design_preferences (LLM)."
    site_info = (state.get("site_info") or "").strip()
    if site_info:
        site_info = site_info + "\n" + note
    else:
        site_info = note
    result = {"design_tokens": tokens, "site_info": site_info}
    result.update(base_out)
    return result


def _has_palette_from_state(state: dict) -> bool:
    t = state.get("design_tokens") or {}
    if not isinstance(t, dict):
        return False
    p = t.get("palette")
    if not isinstance(p, dict) or not p:
        return False
    for v in p.values():
        if isinstance(v, dict) and (v.get("hex") or "").strip():
            return True
        if isinstance(v, str) and v.strip():
            return True
    return False


async def _fallback_parse(llm: Any, messages: list) -> UserDesignExtractResult | None:
    try:
        response = await llm.ainvoke(messages)
        raw = getattr(response, "content", None)
        if isinstance(raw, list):
            raw = " ".join(
                (b.get("text", "") if isinstance(b, dict) else str(b)) for b in raw
            )
        raw = (raw or "").strip() if isinstance(raw, str) else str(raw).strip()
        data = extract_json(raw)
        return UserDesignExtractResult.model_validate(data)
    except Exception:
        return None


def route_after_extract(state: dict) -> str:
    """После извлечения пользовательского дизайна — либо reference-сайт, либо сразу prepare_spec."""
    from agents.generate_agent.nodes.reference_design_nodes import should_run_reference_design_pipeline

    return (
        "run_reference_screenshots"
        if should_run_reference_design_pipeline(state)
        else "prepare_spec_input"
    )
