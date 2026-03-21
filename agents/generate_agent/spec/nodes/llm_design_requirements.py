"""Single LLM step: canonical brief → full design requirements for downstream nodes (execute, summarize).

Replaces the former chain: brand_synthesizer, visual_grammar, typography_director,
layout_dramaturgy, background_filler, media_agent, svg_illustrator, animation_director.
Still runs semantic_parser first (deterministic SessionExport → canonical_spec), then one
structured LLM call to fill brand_profile, design_tokens, typography_spec, layout_spec,
background_spec, animation_spec. Unsplash runs after this node in main.py.
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
from agents.generate_agent.spec.utils.site_target import normalize_site_target
from agents.generate_agent.spec.utils.generation_plan import build_generation_plan

log = logging.getLogger(__name__)

TARGET_MOBILE = """
=== TARGET: MOBILE (phone-first) ===
The site is primarily for smartphones. Shape ALL design requirements for narrow viewports and touch:
- layout_spec: single-column stacks, generous vertical rhythm, thumb-reachable CTAs, avoid side-by-side complexity; grids that collapse to one column; clear section breaks.
- typography_spec: slightly larger body than desktop norms; comfortable line length (~35–45ch max width feel); avoid tiny UI type.
- design_tokens: touch-friendly spacing; motion subtle enough for performance on phones.
- animation_spec: respect reduced motion; avoid hover-only cues (no “reveal on hover” as sole affordance).
- brand_profile image_keywords: favor moods that work with portrait/square photography.
- background_spec: avoid dependency on wide panoramic backgrounds as the only structure.
"""

TARGET_DESKTOP = """
=== TARGET: DESKTOP (PC-first) ===
The site is primarily for large screens. Shape requirements for wide viewports and pointer/hover:
- layout_spec: multi-column sections, horizontal bands, optional asymmetric splits, richer hero widths.
- typography_spec: can use tighter scale hierarchy and wider measure where appropriate.
- design_tokens: can use finer spacing steps; shadows and hover affordances expected where useful.
- animation_spec: hover micro-interactions and scroll-linked motion are welcome.
- brand_profile image_keywords: landscape and cinematic imagery work well.
"""

SYSTEM = """You are a senior product designer and frontend systems architect.
Given CANONICAL_SPEC (structured business/site facts) and SESSION_EXPORT (raw strategy/design),
produce ONE JSON object matching the required keys. Output must be valid for an Astro + Tailwind site.

Rules:
- brand_profile: creative directions, chosen_direction (name, concept, boldness, visual_adjectives),
  tone (voice, formality), hero_headlines[], image_keywords[] (short Unsplash search terms per section mood),
  messages (primary, secondary, trust).
- design_tokens: palette with primary/secondary/accent/background/surface/text/muted as {hex, usage},
  spacing, grid, radius, shadow, motion (level, duration_*, easing), bold_design_move,
  bold_design_move_implementation. Hex colors must be #RRGGBB. Prefer distinctive palettes (not generic purple-on-white).
- typography_spec: primary + secondary FontSpec (family, weights, usage), scale (hero, h1, body, …),
  font_import_urls[] (Google Fonts CSS URLs), tailwind_mapping if useful.
- layout_spec: page, emotional_arc[], sections[] each with id, role, grid, elements[], image_ratio where photos apply,
  background_layer {type, hint, z_index}, ascii_wireframe (short), focal_hierarchy[].
- background_spec: backgrounds[] with section_id, background_type, config, z_index; dependencies if any heavy libs (usually all false for Astro static).
- animation_spec: sections[] with section_id, entrance {type, duration, easing}, optional hover/stagger; global reduced_motion_strategy.

Align section ids with canonical sections_available and content. Be bold and specific — downstream LLMs rely on this.

Follow the TARGET DEVICE block appended below (mobile vs desktop): it overrides generic assumptions about layout density and interaction model."""

MULTI_PAGE = """
=== MULTI-PAGE SITE (more than one route) ===
canonical.pages has multiple entries. Design for a small site with several HTML routes (Astro pages), NOT a single landing only:
- layout_spec: sections describe reusable blocks; home page typically stacks most sections; inner pages may reuse 1–3 components (e.g. page title + content).
- BaseLayout must support a site-wide <nav> listing every page (use session_export.site_pages for titles and paths when present).
- Mention in ascii_wireframe or focal_hierarchy how inner pages differ from home (e.g. simpler layout).
- brand_profile / image_keywords: still apply; inner pages may need calmer imagery.
"""


class LLMDesignRequirementsBundle(BaseModel):
    """Structured bundle for one-shot design pipeline output."""

    model_config = ConfigDict(extra="forbid")
    brand_profile: dict[str, Any] = Field(default_factory=dict)
    design_tokens: dict[str, Any] = Field(default_factory=dict)
    typography_spec: dict[str, Any] = Field(default_factory=dict)
    layout_spec: dict[str, Any] = Field(default_factory=dict)
    background_spec: dict[str, Any] = Field(default_factory=dict)
    animation_spec: dict[str, Any] = Field(default_factory=dict)


def _site_target_for_prompt(state: dict[str, Any]) -> str:
    st = state.get("site_target")
    if isinstance(st, str) and st in ("mobile", "desktop"):
        return st
    c = state.get("canonical_spec") or {}
    if isinstance(c, dict):
        prefs = c.get("preferences") or {}
        if isinstance(prefs, dict):
            return normalize_site_target(prefs.get("site_target"))
    return "desktop"


async def _invoke_bundle_llm(state: dict[str, Any]) -> tuple[LLMDesignRequirementsBundle, list[str]]:
    errors: list[str] = []
    canonical = state.get("canonical_spec") or {}
    session = state.get("session_export") or {}
    site_target = _site_target_for_prompt(state)
    target_block = TARGET_MOBILE if site_target == "mobile" else TARGET_DESKTOP
    page_ids = canonical.get("pages") if isinstance(canonical, dict) else None
    multi_block = ""
    if isinstance(page_ids, list) and len(page_ids) > 1:
        multi_block = MULTI_PAGE
    system_full = SYSTEM + target_block + multi_block
    pb = state.get("page_briefs")
    page_briefs_block = ""
    if isinstance(pb, dict) and pb:
        page_briefs_block = (
            "\n\nPAGE_BRIEFS (Phase 1 — per-page ТЗ already generated; MUST align layout_spec sections, "
            "nav labels, and emotional_arc with these briefs; home is usually the richest page):\n"
            + json.dumps(pb, ensure_ascii=False, indent=2)
            + "\n"
        )
    user = (
        f"SITE_TARGET (canonical preference): {site_target}\n\n"
        "CANONICAL_SPEC:\n"
        + json.dumps(canonical, ensure_ascii=False, indent=2)
        + "\n\nSESSION_EXPORT (strategy/design context):\n"
        + json.dumps(session, ensure_ascii=False, indent=2)
        + page_briefs_block
        + "\n\nReturn a single JSON object with keys: "
        "brand_profile, design_tokens, typography_spec, layout_spec, background_spec, animation_spec."
    )
    llm = get_llm(tier="concept", temperature=0.65, max_tokens=16384)
    messages = [SystemMessage(content=system_full), HumanMessage(content=user)]
    llm_structured = llm.with_structured_output(LLMDesignRequirementsBundle, method="json_schema")
    try:
        result = await llm_structured.ainvoke(messages)
        if result is not None:
            return result, errors
    except Exception as exc:
        log.warning("llm_design_requirements: structured output failed (%s), fallback", exc)
        errors.append(f"[llm_design_requirements] structured: {exc}")

    try:
        response = await llm.ainvoke(messages)
        content = (response.content or "").strip() if hasattr(response, "content") else str(response)
        raw = extract_json(content)
        bundle = LLMDesignRequirementsBundle.model_validate(raw)
        return bundle, errors
    except (LLMJsonError, Exception) as exc:
        errors.append(f"[llm_design_requirements] fallback parse: {exc}")
        return LLMDesignRequirementsBundle(), errors


async def llm_design_requirements(state: dict[str, Any]) -> dict[str, Any]:
    """
    Run semantic_parser if needed (skipped when page_briefs_node already set canonical_spec),
    then one LLM call for all design artifacts. Consumes page_briefs from Phase 1 when present.
    Always sets _spec_done so the sync join can proceed.
    """
    if state.get("canonical_spec"):
        out: dict[str, Any] = {"canonical_spec": state["canonical_spec"]}
        if state.get("errors"):
            out["errors"] = list(state["errors"])
    else:
        parsed = await semantic_parser(state)
        out = dict(parsed)
    if state.get("page_briefs") is not None:
        out["page_briefs"] = state["page_briefs"]

    canonical_spec = out.get("canonical_spec")
    if not canonical_spec:
        out.setdefault("errors", []).append("[llm_design_requirements] missing canonical_spec")
        out["_spec_done"] = True
        return out

    merged: dict[str, Any] = {**state, **out}
    bundle, llm_errors = await _invoke_bundle_llm(merged)
    err_list = list(out.get("errors") or [])
    err_list.extend(llm_errors)

    out.update(
        {
            "brand_profile": bundle.brand_profile,
            "design_tokens": bundle.design_tokens,
            "typography_spec": bundle.typography_spec,
            "layout_spec": bundle.layout_spec,
            "background_spec": bundle.background_spec,
            "animation_spec": bundle.animation_spec,
            "_spec_done": True,
        }
    )
    if err_list:
        out["errors"] = err_list

    merged_final: dict[str, Any] = {**state, **out}
    out["generation_plan"] = build_generation_plan(merged_final)
    return out
