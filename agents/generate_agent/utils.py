# utils.py
"""Shared helpers for generate_agent. Extract user request from messages regardless of format."""

import json
from typing import Any, Optional


def format_reasoning_task(decision: dict, project_path: str) -> str:
    """
    Format reasoning_decision as a clear project-step description for load_skills and execute.
    Both nodes receive the same structured description from reasoning.
    """
    action = decision.get("action", "")
    lines = [
        "PROJECT STEP FROM REASONING",
        "---",
        f"Action: {action}",
        f"Project path: {project_path}",
    ]
    if action == "create_file":
        lines.append(f"File: {decision.get('file_path', '')}")
        lines.append(f"Type: {decision.get('file_type', '')}")
        purpose = decision.get("purpose", "")
        if purpose:
            lines.append(f"Purpose: {purpose}")
        reqs = decision.get("key_requirements", [])
        if reqs:
            lines.append("Key requirements: " + "; ".join(str(r) for r in reqs[:15]))
        skill = decision.get("recommended_skill", "")
        if skill:
            lines.append(f"Recommended skill: {skill}")
    elif action == "shell_command":
        lines.append(f"Command: {decision.get('command', '')}")
        lines.append(f"Working directory: {decision.get('working_directory', project_path)}")
    reasoning = decision.get("reasoning", "")
    if reasoning:
        lines.append(f"Reasoning: {reasoning}")
    lines.append("---")
    return "\n".join(lines)


def _content_to_str(content) -> str:
    """Normalize message content (str or list of blocks) to a single string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return " ".join(parts).strip() if parts else ""
    return str(content).strip()


def _normalize_content_for_api(content: Any) -> str | list:
    """Ensure content is string or array of content blocks for OpenAI API (messages[].content)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Valid content blocks: list of dicts with "type" and "text" or "image_url"
        if all(
            isinstance(b, dict) and b.get("type") in ("text", "image_url")
            for b in content
        ):
            return content
        return json.dumps(content) if content else ""
    if isinstance(content, dict):
        return json.dumps(content)
    return str(content)


def normalize_messages_for_api(messages: list) -> list:
    """
    Return a new list of messages with content normalized to string or array.
    Fixes OpenAI 400: 'messages[N].content must be string or array' when tool
    results or checkpoint state leave content as dict/other.
    """
    from langchain_core.messages import (
        AIMessage,
        BaseMessage,
        HumanMessage,
        SystemMessage,
        ToolMessage,
    )
    out: list[BaseMessage] = []
    for m in messages:
        content = getattr(m, "content", None)
        normalized = _normalize_content_for_api(content)
        if isinstance(m, SystemMessage):
            out.append(SystemMessage(content=normalized))
        elif isinstance(m, HumanMessage):
            out.append(HumanMessage(content=normalized))
        elif isinstance(m, AIMessage):
            out.append(
                AIMessage(
                    content=normalized,
                    tool_calls=getattr(m, "tool_calls", None) or [],
                )
            )
        elif isinstance(m, ToolMessage):
            out.append(
                ToolMessage(
                    content=normalized,
                    tool_call_id=getattr(m, "tool_call_id", "") or "",
                )
            )
        else:
            out.append(HumanMessage(content=normalized))
    return out


def get_user_request(messages: list) -> str:
    """
    Extract the first user/human message content from state['messages'].
    Supports both LangChain message objects (msg.type == 'human', msg.content)
    and dict format from API (msg.get('role') in ('user', 'human'), msg.get('content')).
    """
    if not messages:
        return ""
    for msg in messages:
        content = None
        if hasattr(msg, "type"):
            if getattr(msg, "type", None) == "human":
                content = getattr(msg, "content", None)
        elif isinstance(msg, dict):
            role = msg.get("role") or msg.get("type")
            if role in ("user", "human"):
                content = msg.get("content")
        if content is not None:
            text = _content_to_str(content)
            if text:
                return text
    return ""


def _get_json_data_val(obj: Any, *keys: str) -> Optional[str]:
    """Get a leaf value from json_data nested structure (e.g. brand.name.data)."""
    if not obj or not isinstance(obj, dict):
        return None
    for key in keys:
        obj = obj.get(key) if isinstance(obj, dict) else None
        if obj is None:
            return None
    if isinstance(obj, dict) and "data" in obj:
        val = obj["data"]
        return str(val).strip() if val not in (None, "") else None
    return str(obj).strip() if obj not in (None, "") else None


def build_short_site_info(json_data: Optional[dict], max_length: int = 400) -> str:
    """
    Build a short (1-3 sentence) site summary from json_data for reasoning/load_skills.
    Saves tokens vs full content_brief; execute still gets full brief for generation.
    """
    if not json_data or not isinstance(json_data, dict):
        return ""
    parts = []
    name = _get_json_data_val(json_data, "brand", "name")
    if name:
        parts.append(name)
    tagline = _get_json_data_val(json_data, "brand", "tagline")
    activity = _get_json_data_val(json_data, "business", "activity", "short")
    if tagline:
        parts.append(tagline)
    elif activity:
        parts.append(activity)
    tone = _get_json_data_val(json_data, "brand", "tone_of_text")
    if tone:
        parts.append(f"Тон: {tone}.")
    cta = _get_json_data_val(json_data, "site_goals", "cta", "main")
    if cta:
        parts.append(f"CTA: {cta}.")
    text = " ".join(parts).strip()
    return text[:max_length] if text else ""


def build_content_brief(json_data: Optional[dict], max_lines: int = 120) -> str:
    """
    Build a short content brief from json_data (nested { ..., "data": value }).
    Used so reasoning/action nodes have real brand, CTA, etc. — no generic placeholders.
    """
    if not json_data or not isinstance(json_data, dict):
        return ""

    lines: list[str] = []

    def _extract(obj: Any, prefix: str = "", depth: int = 0) -> None:
        if depth > 4 or len(lines) >= max_lines:
            return
        if isinstance(obj, dict):
            if "data" in obj:
                val = obj["data"]
                if isinstance(val, list):
                    lines.append(f"{prefix}: (list) {len(val)} items")
                    for i, item in enumerate(val[:5]):
                        if isinstance(item, dict) and "text" in item:
                            lines.append(f"  - {item.get('text', item)}")
                        else:
                            lines.append(f"  - {item}")
                elif isinstance(val, (str, int, float, bool)) and val not in (None, ""):
                    lines.append(f"{prefix}: {val}")
                elif val is None or val == "":
                    pass
                return
            for k, v in obj.items():
                if k.startswith("_"):
                    continue
                _extract(v, f"{prefix}.{k}" if prefix else k, depth + 1)
        elif isinstance(obj, list) and obj and prefix:
            lines.append(f"{prefix}: (list) {len(obj)} items")
            for i, item in enumerate(obj[:3]):
                _extract(item, f"{prefix}[{i}]", depth + 1)

    _extract(json_data)
    return "\n".join(lines[:max_lines]) if lines else ""


def get_site_info(state: dict) -> str:
    """
    Short site summary for reasoning/load_skills.
    Prefer spec pipeline (canonical_spec + brand_profile), then project_spec (ТЗ), then json_data/site_info.
    """
    # Spec pipeline: canonical_spec + brand_profile
    canonical = state.get("canonical_spec") or {}
    brand = state.get("brand_profile") or {}
    if isinstance(canonical, dict) and isinstance(brand, dict) and canonical.get("brand") and brand.get("chosen_direction"):
        b = canonical.get("brand", {})
        direction = brand.get("chosen_direction", {})
        parts = [
            b.get("name") or "",
            (direction.get("name") or "") + ": " + (direction.get("concept") or ""),
            "Goal: " + (canonical.get("site_goal") or "leads"),
        ]
        text = " | ".join(p for p in parts if p).strip()
        if text:
            return text[:500]
    spec = state.get("project_spec") or {}
    if isinstance(spec, dict) and spec.get("short_summary"):
        return (spec.get("short_summary") or "").strip()
    if state.get("site_info"):
        return (state.get("site_info") or "").strip()
    return build_short_site_info(state.get("json_data"))


def get_content_brief(state: dict) -> str:
    """
    Full content brief for execute/reasoning.
    Prefer spec pipeline (canonical_spec + brand_profile), then project_spec, then json_data.
    """
    canonical = state.get("canonical_spec") or {}
    brand = state.get("brand_profile") or {}
    if isinstance(canonical, dict) and isinstance(brand, dict) and canonical.get("content"):
        lines = []
        content = canonical.get("content", {})
        for key in ("hero_headline_seed", "offer_text", "usp_text", "guarantees_text", "work_hours", "address"):
            v = content.get(key)
            if v and isinstance(v, str) and v.strip():
                lines.append(f"{key}: {v.strip()}")
        msgs = brand.get("messages") or {}
        if isinstance(msgs, dict):
            for k in ("primary", "secondary", "trust"):
                v = msgs.get(k)
                if v and isinstance(v, str):
                    lines.append(f"message_{k}: {v}")
        headlines = brand.get("hero_headlines") or []
        if headlines:
            lines.append("hero_headlines: " + " | ".join(str(h) for h in headlines[:5]))
        if lines:
            return "\n".join(lines)
    spec = state.get("project_spec") or {}
    if isinstance(spec, dict) and spec.get("content_brief"):
        return (spec.get("content_brief") or "").strip()
    return build_content_brief(state.get("json_data"))


def get_spec_sections(state: dict) -> list:
    """Ordered section names. Prefer layout_spec (spec pipeline), then project_spec, then site_architecture."""
    layout = state.get("layout_spec") or {}
    if isinstance(layout, dict):
        sections = layout.get("sections") or []
        if sections:
            return [s.get("id") or s.get("role") or "section" for s in sections if isinstance(s, dict)]
    spec = state.get("project_spec") or {}
    if isinstance(spec, dict) and spec.get("sections") is not None:
        return spec.get("sections") or []
    arch = state.get("site_architecture") or {}
    return arch.get("sections", [])


def get_spec_blocks(state: dict) -> list:
    """Blocks (type + content) per section. Prefer layout_spec (spec pipeline), then project_spec, then site_architecture."""
    layout = state.get("layout_spec") or {}
    if isinstance(layout, dict):
        sections = layout.get("sections") or []
        if sections:
            blocks = []
            for s in sections:
                if not isinstance(s, dict):
                    continue
                blocks.append({
                    "type": s.get("id") or s.get("role") or "section",
                    "content": {"role": s.get("role"), "grid": s.get("grid"), "elements": s.get("elements", [])},
                })
            if blocks:
                return blocks
    spec = state.get("project_spec") or {}
    if isinstance(spec, dict) and spec.get("blocks") is not None:
        return spec.get("blocks") or []
    arch = state.get("site_architecture") or {}
    return arch.get("blocks", [])


def get_design_spec(state: dict) -> Optional[dict]:
    """Design spec (palette, typography, mood, key_requirements). Prefer spec pipeline (design_tokens + typography_spec + brand_profile), then project_spec."""
    tokens = state.get("design_tokens") or {}
    typo = state.get("typography_spec") or {}
    brand = state.get("brand_profile") or {}
    if isinstance(tokens, dict) and (tokens.get("palette") or tokens.get("motion")):
        direction = (brand or {}).get("chosen_direction") or {}
        palette = tokens.get("palette") or {}
        primary_font = (typo.get("primary") or {}).get("family") if isinstance(typo, dict) else None
        secondary_font = (typo.get("secondary") or {}).get("family") if isinstance(typo, dict) else None
        adj = direction.get("visual_adjectives") or []
        mood = (direction.get("concept") or "") + "; " + ", ".join(str(x) for x in adj)
        key_requirements = list(adj) + [tokens.get("bold_design_move") or ""]
        key_requirements = [str(r) for r in key_requirements if r]
        return {
            "palette": {k: v.get("hex") if isinstance(v, dict) else str(v) for k, v in palette.items()} if isinstance(palette, dict) else {},
            "typography": f"Primary: {primary_font}; Secondary: {secondary_font}" if (primary_font or secondary_font) else "",
            "mood": mood.strip("; "),
            "key_requirements": key_requirements,
        }
    spec = state.get("project_spec") or {}
    if not isinstance(spec, dict):
        return None
    design = spec.get("design")
    return design if isinstance(design, dict) else None


def get_design_brief(state: dict) -> Optional[str]:
    """Full design concept for execute. Prefer spec pipeline (layout_spec + design_tokens + typography_spec + background_spec + animation_spec), then project_spec.design_brief."""
    layout = state.get("layout_spec") or {}
    tokens = state.get("design_tokens") or {}
    typo = state.get("typography_spec") or {}
    background = state.get("background_spec") or {}
    animation = state.get("animation_spec") or {}
    asset_manifest = state.get("asset_manifest") or {}
    if isinstance(layout, dict) and layout.get("sections"):
        parts = ["=== SPEC PIPELINE DESIGN BRIEF ===\n"]
        parts.append("SECTIONS (order and structure):")
        for s in layout.get("sections", []):
            if isinstance(s, dict):
                parts.append(f"  - {s.get('id', s.get('role', '?'))}: grid={s.get('grid')}, role={s.get('role')}, background_layer={s.get('background_layer')}")
        if layout.get("ascii_wireframe"):
            parts.append("\nASCII WIREFRAME:\n" + (layout.get("ascii_wireframe") or "")[:2000])
        if isinstance(tokens, dict) and tokens.get("palette"):
            parts.append("\nPALETTE (use these hex in Tailwind/custom.css):")
            for k, v in (tokens.get("palette") or {}).items():
                if isinstance(v, dict) and v.get("hex"):
                    parts.append(f"  {k}: {v['hex']}")
            if tokens.get("bold_design_move"):
                parts.append("Bold design move: " + str(tokens.get("bold_design_move")))
            if tokens.get("motion"):
                parts.append("Motion: " + str(tokens.get("motion")))
        if isinstance(typo, dict) and (typo.get("primary") or typo.get("secondary")):
            parts.append("\nTYPOGRAPHY:")
            for key in ("primary", "secondary"):
                f = typo.get(key)
                if isinstance(f, dict):
                    parts.append(f"  {key}: {f.get('family')} weights {f.get('weights', [])}")
            if typo.get("font_import_urls"):
                urls = typo.get("font_import_urls") or []
                urls = list(urls.values()) if isinstance(urls, dict) else (urls if isinstance(urls, list) else [])
                parts.append("Font import URLs: " + ", ".join(str(u) for u in urls[:5]))
        if isinstance(background, dict) and background.get("backgrounds"):
            parts.append("\nBACKGROUNDS per section:")
            bgs = background.get("backgrounds") or []
            bgs = list(bgs.values()) if isinstance(bgs, dict) else bgs
            for bg in (bgs if isinstance(bgs, list) else [])[:15]:
                if isinstance(bg, dict):
                    parts.append(f"  {bg.get('section_id')}: type={bg.get('background_type')}, config={bg.get('config')}")
        if isinstance(animation, dict) and animation.get("sections"):
            parts.append("\nANIMATIONS (entrance, hover, parallax per section):")
            anim_sections = animation.get("sections") or []
            anim_sections = list(anim_sections.values()) if isinstance(anim_sections, dict) else anim_sections
            for a in (anim_sections if isinstance(anim_sections, list) else [])[:10]:
                if isinstance(a, dict):
                    parts.append(f"  {a.get('section_id')}: entrance={a.get('entrance')}")
        if isinstance(asset_manifest, dict) and (asset_manifest.get("images") or asset_manifest.get("icons")):
            imgs = asset_manifest.get("images") or []
            imgs = list(imgs.values()) if isinstance(imgs, dict) else (imgs if isinstance(imgs, list) else [])
            parts.append("\nASSET IMAGES (role -> url): " + ", ".join(f"{i.get('role')}={i.get('url') or i.get('local_path')}" for i in imgs[:8] if isinstance(i, dict)))
        parts.append("""
SECTION COMPOSITION — ANTI-TEMPLATE (mandatory):
- Do NOT use the same layout for every section: avoid "centered headline + 3 equal cards" everywhere.
- Use asymmetric grids (e.g. 60-40, one large + two small), varied section heights, and different alignments (left, right, centered) so the page has rhythm.
- Each section must have ONE clear focal point; avoid uniform grids of identical blocks (e.g. 4 identical feature cards).
- Vary spacing between sections; avoid identical padding/margin on every section.
- One section should feel like the "bold move" (full-bleed, oversized type, or strong visual break).
- The result must NOT look like a generic AI/Webflow template: no hero → 3 cards → testimonials → CTA cookie-cutter.
""")
        parts.append("\n=== END SPEC PIPELINE BRIEF ===")
        return "\n".join(parts)
    spec = state.get("project_spec") or {}
    if not isinstance(spec, dict):
        return None
    brief = spec.get("design_brief")
    return (brief or "").strip() if isinstance(brief, str) else None


def get_spec_pipeline_mandate(state: dict) -> str:
    """
    Short mandatory block from spec pipeline: component order, palette, CTA, typography.
    Use this in reasoning and execute so generation strictly follows the spec JSON.
    Returns empty string when no spec pipeline data.
    """
    layout = state.get("layout_spec") or {}
    tokens = state.get("design_tokens") or {}
    typo = state.get("typography_spec") or {}
    canonical = state.get("canonical_spec") or {}
    if not isinstance(layout, dict) or not layout.get("sections"):
        return ""

    parts = ["=== SPEC PIPELINE (MANDATORY — use this for generation) ==="]

    st = state.get("site_target")
    if st is None and isinstance(canonical, dict):
        prefs = canonical.get("preferences") or {}
        if isinstance(prefs, dict):
            st = prefs.get("site_target")
    if st == "mobile":
        parts.append(
            "SITE TARGET: mobile-first — optimize for narrow viewports and touch; single-column flow, "
            "no hover-only interactions, comfortable tap targets (~44px min), readable type."
        )
    elif st == "desktop":
        parts.append(
            "SITE TARGET: desktop-first — optimize for wide viewports; multi-column layouts and hover affordances allowed."
        )

    # Component order: section id -> ComponentName.astro
    sections = layout.get("sections", [])
    comp_names = []
    for s in sections:
        if not isinstance(s, dict):
            continue
        sid = (s.get("id") or s.get("role") or "section").strip()
        if not sid:
            continue
        # hero -> Hero.astro, features -> Features.astro, testimonials -> Testimonials.astro
        name = sid.replace("_", " ").title().replace(" ", "") + ".astro"
        comp_names.append(name)
    if comp_names:
        parts.append("COMPONENT ORDER (create .astro files in this order): " + ", ".join(comp_names))
        parts.append("In index.astro import and render home sections in this order (inner pages may use a subset).")
        pages_ids = canonical.get("pages") if isinstance(canonical, dict) else []
        if isinstance(pages_ids, list) and len(pages_ids) > 1:
            parts.append(
                "MULTI-PAGE: create every route in generation_plan — index.astro for home plus src/pages/<slug>.astro "
                "for other ids; BaseLayout must include navigation to all routes."
            )
        parts.append("Section layout: use asymmetric grids and varied composition per section — avoid identical centered blocks; one focal point per section.")

    # Palette
    if isinstance(tokens, dict) and tokens.get("palette"):
        palette = tokens.get("palette", {})
        hexes = []
        for k, v in palette.items():
            if isinstance(v, dict) and v.get("hex"):
                hexes.append(f"{k}={v['hex']}")
        if hexes:
            parts.append("PALETTE (use in Tailwind/custom.css :root or classes): " + ", ".join(hexes))

    # Primary CTA
    if isinstance(canonical, dict) and canonical.get("primary_cta"):
        cta = canonical["primary_cta"]
        if isinstance(cta, dict):
            label = cta.get("label") or "Связаться"
            link = cta.get("link") or "#contact-form"
            action = cta.get("action") or "form"
            parts.append(f"PRIMARY CTA: label=\"{label}\", link=\"{link}\", action={action}")

    # Typography
    if isinstance(typo, dict) and (typo.get("primary") or typo.get("secondary")):
        p = (typo.get("primary") or {}).get("family") if isinstance(typo.get("primary"), dict) else None
        s = (typo.get("secondary") or {}).get("family") if isinstance(typo.get("secondary"), dict) else None
        if p or s:
            parts.append("TYPOGRAPHY: heading=" + (p or "—") + ", body=" + (s or "—"))
        urls = typo.get("font_import_urls") or []
        if urls:
            parts.append("Font import URLs (add to layout head): " + "; ".join(urls[:3]))

    parts.append("=== END SPEC PIPELINE MANDATE ===\n")
    return "\n".join(parts)


def format_page_brief_for_path(state: dict, file_path: str) -> str:
    """
    Phase 1 per-page brief (page_briefs) for this file path, or empty.
    Used for src/pages/*.astro when page_briefs_node ran before llm_design_requirements.
    """
    from agents.generate_agent.spec.utils.site_pages import src_path_to_page_id

    pb = state.get("page_briefs") or {}
    canonical = state.get("canonical_spec") or {}
    if not isinstance(pb, dict) or not pb:
        return ""
    ids = canonical.get("pages") if isinstance(canonical.get("pages"), list) else []
    if not ids:
        return ""
    pid = src_path_to_page_id(file_path, [str(x) for x in ids])
    if not pid or pid not in pb:
        return ""
    return json.dumps(pb[pid], ensure_ascii=False, indent=2)
