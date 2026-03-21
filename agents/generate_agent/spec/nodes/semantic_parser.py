"""SessionExport -> CanonicalSpec (no LLM)."""
from __future__ import annotations

from typing import Any

from agents.generate_agent.spec.utils.schema_validator import validate
from agents.generate_agent.spec.utils.site_target import normalize_site_target
from agents.generate_agent.spec.utils.site_pages import parse_site_pages

PRICE_MAP: dict[str | None, str] = {
    "Низкий": "low", "Средний": "medium", "Высокий": "high", "Индивидуально": "custom", None: "medium",
}
GOAL_MAP: dict[str | None, str] = {
    "Продажи": "sales", "Заявки": "leads", "Доверие": "trust", "Презентация": "presentation", None: "leads",
}
TYPO_DENSITY_MAP: dict[str | None, str] = {
    "Минимум текста": "minimal", "Средний объём": "medium", "Много текста": "heavy", None: "medium",
}
ANIM_MAP: dict[str | None, str] = {
    "Без анимаций": "none", "Деликатные": "subtle", "Средние": "medium", "Максимум": "max", None: "subtle",
}
CTA_PRIORITY: dict[str, list[str]] = {
    "sales": ["phone", "whatsapp", "telegram", "form"],
    "leads": ["form", "phone", "whatsapp", "telegram"],
    "trust": ["phone", "form", "telegram", "whatsapp"],
    "presentation": ["form", "telegram", "phone", "whatsapp"],
}
CTA_LABELS: dict[str, str] = {
    "phone": "Позвонить", "whatsapp": "Написать в WhatsApp",
    "telegram": "Написать в Telegram", "form": "Оставить заявку",
}


def _derive_sections(design: dict) -> dict[str, bool]:
    strategy = design.get("_strategy", {})
    return {
        "hero": True,
        "features": bool(strategy.get("offer") or strategy.get("usp")),
        "cases": design.get("cases") is not None,
        "testimonials": bool(design.get("reviews") or design.get("social_proof")),
        "team": design.get("team") is not None,
        "faq": design.get("faq") is not None,
        "achievements": design.get("achievements") is not None,
        "certificates": design.get("certificates") is not None,
        "social_proof": design.get("social_proof") is not None,
    }


def _derive_primary_cta(site_goal: str, contacts: dict) -> dict[str, Any]:
    priority = CTA_PRIORITY.get(site_goal, CTA_PRIORITY["leads"])
    available: dict[str, str] = {}
    for channel, (toggle_key, link_key) in {
        "phone": ("phone", "phone_link"),
        "whatsapp": ("whatsapp", "whatsapp_link"),
        "telegram": ("telegram", "telegram_link"),
        "form": ("form", "form_link"),
    }.items():
        if contacts.get(toggle_key):
            link = contacts.get(link_key) or ""
            if channel == "phone" and link and not link.startswith("tel:"):
                link = f"tel:{link}"
            available[channel] = link
    chosen = next((ch for ch in priority if ch in available), "form")
    return {
        "label": CTA_LABELS.get(chosen, "Связаться"),
        "action": chosen,
        "link": available.get(chosen, "#contact-form"),
        "channels": [{"type": ch, "link": lnk} for ch, lnk in available.items()],
    }


def _build_canonical(raw: dict) -> dict[str, Any]:
    strategy: dict = raw.get("strategy", {})
    design: dict = raw.get("design", {})
    rkn: dict = raw.get("rkn", {})
    page_ids, _page_details = parse_site_pages(raw)
    contacts: dict = strategy.get("contacts", {})
    site_goal = GOAL_MAP.get(strategy.get("site_goal"))
    price_segment = PRICE_MAP.get(strategy.get("price"))
    design_with_strategy = {**design, "_strategy": strategy}
    sections = _derive_sections(design_with_strategy)
    brand_name = strategy.get("brand_name", "")
    activity = strategy.get("activity", "")
    usp = strategy.get("usp", "")

    return {
        "session_id": raw.get("session_id", "unknown"),
        "brand": {
            "name": brand_name, "activity": activity, "audience": strategy.get("audience"),
            "positioning": strategy.get("positioning"), "usp": usp, "geo": strategy.get("geo"),
            "competitors": strategy.get("competitors"), "exclude_clients": strategy.get("exclude_clients"),
            "offer": strategy.get("offer"), "guarantees": strategy.get("guarantees"),
            "objections": strategy.get("objections"),
        },
        "pages": page_ids,
        "sections_available": sections,
        "primary_cta": _derive_primary_cta(site_goal, contacts),
        "secondary_cta": None,
        "content": {
            "hero_headline_seed": " — ".join(filter(None, [brand_name, activity, usp])),
            "offer_text": strategy.get("offer"), "usp_text": usp, "guarantees_text": strategy.get("guarantees"),
            "work_hours": strategy.get("work_hours"), "address": strategy.get("address"),
            "faq_raw": design.get("faq"), "reviews_raw": design.get("reviews"),
            "cases_desc": design.get("cases_desc"), "team_name": design.get("team_name"),
            "team_desc": design.get("team_desc"), "achievements_text": design.get("achievements"),
        },
        "assets": {
            "logo": design.get("logo"), "materials": design.get("materials"),
            "team_photo": design.get("team_photo"), "cases_images": design.get("cases"),
            "certificates": design.get("certificates"),
        },
        "preferences": {
            "style": design.get("style"),
            "typography_density": TYPO_DENSITY_MAP.get(design.get("typography")),
            "animation_level": ANIM_MAP.get(design.get("animations")),
            "site_target": normalize_site_target(raw.get("site_target")),
        },
        "site_goal": site_goal,
        "price_segment": price_segment,
        "legal": {
            "rkn_type": rkn.get("rkn_type"), "name": rkn.get("name"), "inn": rkn.get("inn"),
            "ogrn": rkn.get("ogrn"), "ogrnip": rkn.get("ogrnip"), "kpp": rkn.get("kpp"),
            "address": rkn.get("address"), "email": rkn.get("email"), "phone": rkn.get("phone"),
            "city": rkn.get("city"),
        },
    }


def _get_raw_export(state: dict[str, Any]) -> dict[str, Any] | None:
    """Get SessionExport dict from state. Same sources as prepare_spec_input (fallback if session_export was dropped)."""
    raw = state.get("session_export") or state.get("json_data") or state.get("raw_input")
    if isinstance(raw, dict) and "session_export" in raw and "strategy" not in raw:
        raw = raw.get("session_export", raw)
    if isinstance(raw, dict) and "strategy" in raw:
        return raw
    if isinstance(state.get("input"), dict):
        inp = state["input"]
        raw = inp.get("json_data") or inp.get("session_export")
        if isinstance(raw, dict) and "strategy" in raw:
            return raw
        if isinstance(inp, dict) and "strategy" in inp:
            return inp
    if isinstance(state.get("strategy"), dict) and isinstance(state.get("design"), dict):
        out = {"strategy": state["strategy"], "design": state["design"]}
        if state.get("rkn") is not None:
            out["rkn"] = state["rkn"]
        return out
    return None


async def semantic_parser(state: dict[str, Any]) -> dict[str, Any]:
    raw = _get_raw_export(state)
    if not raw or not isinstance(raw, dict) or "strategy" not in raw:
        raise KeyError(
            "session_export с ключом 'strategy' не найден. "
            "В Input передайте json_data в формате SessionExport: объект с ключами strategy и design. "
            "Пример: agents/generate_agent/spec/langgraph_input_example.json"
        )
    canonical = _build_canonical(raw)
    errors = validate(canonical, "canonical_spec.schema.json")
    if errors:
        return {
            "canonical_spec": canonical,
            "errors": [f"[semantic_parser] {e}" for e in errors],
        }
    return {"canonical_spec": canonical}
