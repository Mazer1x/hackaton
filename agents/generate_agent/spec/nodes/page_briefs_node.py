"""Phase 1: per-page briefs from guideline bundle (guideline + business_requirements). Runs before spec_finalize."""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from agents.generate_agent.spec.utils.json_extract import LLMJsonError, extract_json
from agents.generate_agent.spec.utils.llm import get_llm
from agents.generate_agent.spec.utils.site_target import normalize_site_target
from agents.generate_agent.spec.utils.llm_image_attachment import (
    merge_bundle_image_urls,
    human_message_text_and_images,
)

log = logging.getLogger(__name__)


def _content_block_str(b: Any) -> str:
    if not isinstance(b, dict):
        return str(b)
    if b.get("type") == "text" or "text" in b:
        return str(b.get("text") or "")
    if b.get("type") == "image_url":
        iu = b.get("image_url")
        if isinstance(iu, dict):
            return str(iu.get("url") or "")
        return str(iu or "")
    return str(b)


def _response_content_to_str(response: Any) -> str:
    c = getattr(response, "content", None) if response is not None else None
    if c is None:
        return ""
    if isinstance(c, list):
        return " ".join(_content_block_str(b) for b in c).strip()
    return str(c).strip()


def _bundle_from_state(state: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    jd = state.get("json_data") or {}
    if not isinstance(jd, dict):
        return "", "", {}
    guid = jd.get("guideline")
    guideline = guid.strip() if isinstance(guid, str) else ""
    br = jd.get("business_requirements")
    business_req = br.strip() if isinstance(br, str) else ""
    prefs = jd.get("user_preferences")
    user_prefs = prefs if isinstance(prefs, dict) else {}
    return guideline, business_req, user_prefs


PAGE_BRIEF_SYSTEM = """You are a product writer and information architect.
Given the site GUIDELINE (reference content), BUSINESS_REQUIREMENTS (structured brief or template), and USER_PREFERENCES,
write a focused brief for exactly ONE page (identified below).

Rules:
- Respect brand, audience, and goals implied by the guideline and business requirements.
- If the prompt includes "USER REFERENCE IMAGES" with a list of URLs, sections_outline MUST include places that show those images (e.g. Hero, Gallery, Works) and design_notes must say to embed the exact https URLs in markup.
- sections_outline: ordered list of section names/roles for THIS page only (e.g. Hero, Timeline, FAQ). Home is usually richer; inner pages are often simpler.
- components_hint: optional PascalCase Astro component names that might be specific to this page (can be empty).
- nav_label: short label for the site navigation (same language as the site).
- design_notes: layout/imagery hints for this route only; stay consistent with the guideline.
- If site_target is mobile: note responsive behavior (breakpoints) so desktop view is not an empty margin around a tiny strip.

Output must match the JSON schema (structured output)."""


class PageBrief(BaseModel):
    """Structured brief for one route."""

    model_config = ConfigDict(extra="forbid")
    page_id: str
    title: str = ""
    nav_label: str = ""
    route_hint: str = ""
    purpose: str = ""
    sections_outline: list[str] = Field(default_factory=list)
    content_focus: str = ""
    design_notes: str = ""
    components_hint: list[str] = Field(default_factory=list)


class PageList(BaseModel):
    """Logical page ids for the site (from guideline + requirements)."""

    model_config = ConfigDict(extra="forbid")
    pages: list[str] = Field(default_factory=lambda: ["home"])
    site_target: str = "desktop"


PAGE_LIST_SYSTEM = """You are an information architect. Given the site GUIDELINE and BUSINESS_REQUIREMENTS,
propose a minimal list of logical page ids for the site (e.g. home, about, services, contact).
Rules:
- If the prompt includes "USER REFERENCE IMAGES", the site must be able to show those assets (at minimum a rich "home" with gallery/works is appropriate).
- Always include "home" as the main landing page id unless the site is strictly single-section (then still use "home").
- Use lowercase English identifiers: home, about, pricing, contact, etc.
- For a simple one-page site return exactly: ["home"].
- site_target: "mobile" or "desktop" — infer from requirements or default "desktop".
- If site_target is "mobile": the deliverable is still a normal website in the repo; it must be mobile-first but responsive on md/lg (not a fixed narrow column on desktop).
Output JSON only via schema."""


def _design_tokens_block(state: dict[str, Any]) -> str:
    t = state.get("design_tokens") or {}
    if not isinstance(t, dict) or not t.get("palette"):
        return ""
    return (
        "\n\nRESOLVED DESIGN TOKENS (palette/mood from user text or reference — stay consistent):\n"
        + json.dumps(t, ensure_ascii=False, indent=2)[:6000]
    )


async def _infer_pages(
    guideline: str,
    business_req: str,
    user_prefs: dict[str, Any],
    design_tokens_extras: str = "",
    bundle_image_urls: list[str] | None = None,
) -> PageList:
    prefs_json = json.dumps(user_prefs, ensure_ascii=False, indent=2) if user_prefs else "{}"
    user = (
        f"USER_PREFERENCES:\n{prefs_json}\n\nGUIDELINE (excerpt, may be long):\n{guideline[:8000]}\n\n"
        f"BUSINESS_REQUIREMENTS:\n{business_req[:12000]}\n"
        f"{design_tokens_extras}\n\nReturn pages + site_target."
    )
    llm = get_llm(tier="concept", temperature=0.35, max_tokens=2048)
    human = human_message_text_and_images(user, bundle_image_urls or [])
    messages = [SystemMessage(content=PAGE_LIST_SYSTEM), human]
    llm_so = llm.with_structured_output(PageList, method="json_schema")
    try:
        out = await llm_so.ainvoke(messages)
        if out is not None and out.pages:
            return out
    except Exception as exc:
        log.warning("page_briefs: infer pages structured failed (%s), fallback", exc)
    try:
        response = await llm.ainvoke(messages)
        content = _response_content_to_str(response)
        raw = extract_json(content)
        return PageList.model_validate(raw)
    except (LLMJsonError, Exception) as exc:
        log.warning("page_briefs: infer pages fallback failed (%s)", exc)
        return PageList(pages=["home"], site_target="desktop")


async def _one_page_brief(
    guideline: str,
    business_req: str,
    user_prefs: dict[str, Any],
    page_id: str,
    site_target: str,
    design_tokens_extras: str = "",
    bundle_image_urls: list[str] | None = None,
) -> tuple[PageBrief | None, str | None]:
    prefs_json = json.dumps(user_prefs, ensure_ascii=False, indent=2) if user_prefs else "{}"
    detail = json.dumps(
        {"target_page_id": page_id, "site_target": site_target},
        ensure_ascii=False,
        indent=2,
    )
    user = (
        f"{detail}\n\nUSER_PREFERENCES:\n{prefs_json}\n\nGUIDELINE:\n{guideline[:12000]}\n\n"
        f"BUSINESS_REQUIREMENTS:\n{business_req[:12000]}\n"
        f"{design_tokens_extras}\n\nProduce the PageBrief JSON for this page only."
    )
    llm = get_llm(tier="concept", temperature=0.55, max_tokens=4096)
    human = human_message_text_and_images(user, bundle_image_urls or [])
    messages = [SystemMessage(content=PAGE_BRIEF_SYSTEM), human]
    llm_so = llm.with_structured_output(PageBrief, method="json_schema")
    try:
        out = await llm_so.ainvoke(messages)
        if out is not None:
            return out, None
    except Exception as exc:
        log.warning("page_briefs: structured failed for %s (%s), fallback", page_id, exc)
    try:
        response = await llm.ainvoke(messages)
        content = _response_content_to_str(response)
        raw = extract_json(content)
        b = PageBrief.model_validate(raw)
        return b, None
    except (LLMJsonError, Exception) as exc:
        return None, str(exc)


async def page_briefs_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Build page_briefs from guideline bundle json_data. Does not set _spec_done (spec_finalize does).
    """
    guideline, business_req, user_prefs = _bundle_from_state(state)
    if not guideline and not business_req:
        err = "[page_briefs] json_data must include guideline and/or business_requirements"
        return {"errors": list(state.get("errors") or []) + [err]}

    dt_extra = _design_tokens_block(state)
    jd = state.get("json_data") or {}
    bundle_imgs = merge_bundle_image_urls(jd if isinstance(jd, dict) else {})
    page_list = await _infer_pages(guideline, business_req, user_prefs, dt_extra, bundle_imgs)
    page_ids = [str(p).strip() for p in page_list.pages if str(p).strip()] or ["home"]
    st_merge = normalize_site_target(page_list.site_target or state.get("site_target"))
    site_target = str(st_merge).strip().lower() if st_merge else "desktop"

    out: dict[str, Any] = {"site_target": site_target}
    page_briefs: dict[str, Any] = {}
    err_list = list(state.get("errors") or [])

    for pid in page_ids:
        brief, err = await _one_page_brief(
            guideline, business_req, user_prefs, pid, site_target, dt_extra, bundle_imgs
        )
        if brief is not None:
            data = brief.model_dump()
            data["page_id"] = pid
            page_briefs[pid] = data
        else:
            page_briefs[pid] = {
                "page_id": pid,
                "title": pid,
                "nav_label": pid,
                "purpose": "",
                "sections_outline": [],
                "content_focus": "",
                "design_notes": "",
                "error": err or "unknown",
            }
            err_list.append(f"[page_briefs] {pid}: {err}")

    out["page_briefs"] = page_briefs
    if err_list:
        out["errors"] = err_list
    return out
