"""Phase 1: per-page briefs from one ТЗ (session_export). Runs before llm_design_requirements.

For each canonical page id, one LLM call produces structured copy/UX notes; results in state.page_briefs.
Downstream global design + generation_plan consume these briefs.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from agents.generate_agent.spec.nodes.semantic_parser import semantic_parser
from agents.generate_agent.spec.utils.json_extract import LLMJsonError, extract_json
from agents.generate_agent.spec.utils.llm import get_llm

log = logging.getLogger(__name__)

PAGE_BRIEF_SYSTEM = """You are a product writer and information architect.
Given the full SESSION_EXPORT (ТЗ: strategy, design, site_pages) and CANONICAL_SPEC, write a focused brief for exactly ONE page (identified below).

Rules:
- Respect brand, audience, and goals from the ТЗ.
- sections_outline: ordered list of section names/roles for THIS page only (e.g. Hero, Timeline, FAQ). Home is usually richer; inner pages are often simpler.
- components_hint: optional PascalCase Astro component names that might be specific to this page (can be empty).
- nav_label: short label for the site navigation (same language as the site).
- design_notes: layout/imagery hints for this route only; stay consistent with global style later.

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


async def _one_page_brief(
    merged_state: dict[str, Any],
    page_id: str,
    site_target: str,
) -> tuple[PageBrief | None, str | None]:
    canonical = merged_state.get("canonical_spec") or {}
    session = merged_state.get("session_export") or {}
    detail = json.dumps(
        {
            "target_page_id": page_id,
            "site_target": site_target,
            "canonical_pages": canonical.get("pages"),
        },
        ensure_ascii=False,
        indent=2,
    )
    user = (
        f"{detail}\n\nCANONICAL_SPEC:\n"
        + json.dumps(canonical, ensure_ascii=False, indent=2)
        + "\n\nSESSION_EXPORT:\n"
        + json.dumps(session, ensure_ascii=False, indent=2)
        + "\n\nProduce the PageBrief JSON for this page only."
    )
    llm = get_llm(tier="concept", temperature=0.55, max_tokens=4096)
    messages = [SystemMessage(content=PAGE_BRIEF_SYSTEM), HumanMessage(content=user)]
    llm_so = llm.with_structured_output(PageBrief, method="json_schema")
    try:
        out = await llm_so.ainvoke(messages)
        if out is not None:
            return out, None
    except Exception as exc:
        log.warning("page_briefs: structured failed for %s (%s), fallback", page_id, exc)
    try:
        response = await llm.ainvoke(messages)
        content = (response.content or "").strip() if hasattr(response, "content") else str(response)
        raw = extract_json(content)
        b = PageBrief.model_validate(raw)
        return b, None
    except (LLMJsonError, Exception) as exc:
        return None, str(exc)


async def page_briefs_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Run semantic_parser, then for each page in canonical.pages generate PageBrief (loop).
    Returns canonical_spec + page_briefs. Does not set _spec_done (llm_design_requirements does).
    """
    parsed = await semantic_parser(state)
    out: dict[str, Any] = dict(parsed)
    canonical = out.get("canonical_spec")
    if not canonical:
        out.setdefault("errors", []).append("[page_briefs] missing canonical_spec")
        return out

    merged: dict[str, Any] = {**state, **out}
    page_ids = canonical.get("pages") if isinstance(canonical.get("pages"), list) else ["home"]
    page_ids = [str(p).strip() for p in page_ids if str(p).strip()] or ["home"]

    prefs = canonical.get("preferences") or {}
    st = merged.get("site_target") or (
        (prefs.get("site_target") if isinstance(prefs, dict) else None) or "desktop"
    )
    site_target = str(st).strip().lower() if st else "desktop"

    page_briefs: dict[str, Any] = {}
    err_list = list(out.get("errors") or [])

    for pid in page_ids:
        brief, err = await _one_page_brief(merged, pid, site_target)
        if brief is not None:
            data = brief.model_dump()
            data["page_id"] = pid
            page_briefs[pid] = data
            merged["page_briefs"] = page_briefs
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
            merged["page_briefs"] = page_briefs

    out["page_briefs"] = page_briefs
    if err_list:
        out["errors"] = err_list
    return out
