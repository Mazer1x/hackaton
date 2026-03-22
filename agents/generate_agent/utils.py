# utils.py
"""Shared helpers for generate_agent. Extract user request from messages regardless of format."""

import json
import re
from typing import Any, Optional

from agents.generate_agent.component_naming import component_filename_from_section_key


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


def layout_spec_from_page_briefs(state: dict) -> dict | None:
    """Synthetic layout_spec.sections from page_briefs.sections_outline for analyze / tooling."""
    pb = state.get("page_briefs")
    if not isinstance(pb, dict) or not pb:
        return None
    sections: list[dict] = []
    seen: set[str] = set()
    keys = list(pb.keys())
    if "home" in keys:
        keys = ["home"] + [k for k in keys if k != "home"]
    for key in keys:
        data = pb.get(key)
        if not isinstance(data, dict):
            continue
        for name in data.get("sections_outline") or []:
            if not isinstance(name, str):
                continue
            tokens = re.findall(r"[a-z0-9]+", name.lower())
            sid = "_".join(tokens) if tokens else ""
            if sid and sid not in seen:
                seen.add(sid)
                sections.append({"id": sid, "role": sid})
    return {"sections": sections} if sections else None


def get_site_info(state: dict) -> str:
    """
    Short site summary for reasoning/load_skills.
    Prefer project_spec, guideline bundle (json_data), site_info, then legacy json_data fields.
    """
    jd = state.get("json_data")
    if isinstance(jd, dict):
        gl = jd.get("guideline")
        if isinstance(gl, str) and gl.strip():
            one_line = " ".join(gl.strip().split())[:500]
            if one_line:
                return one_line
    spec = state.get("project_spec") or {}
    if isinstance(spec, dict) and spec.get("short_summary"):
        return (spec.get("short_summary") or "").strip()
    if state.get("site_info"):
        return (state.get("site_info") or "").strip()
    return build_short_site_info(state.get("json_data"))


def get_content_brief(state: dict) -> str:
    """
    Full content brief for execute/reasoning.
    Prefer business_requirements (guideline bundle), project_spec, then nested json_data.
    """
    jd = state.get("json_data")
    if isinstance(jd, dict):
        br = jd.get("business_requirements")
        if isinstance(br, str) and br.strip():
            return br.strip()[:20000]
    spec = state.get("project_spec") or {}
    if isinstance(spec, dict) and spec.get("content_brief"):
        return (spec.get("content_brief") or "").strip()
    return build_content_brief(state.get("json_data"))


def get_spec_sections(state: dict) -> list:
    """Ordered section names. Prefer page_briefs (home), project_spec, site_architecture."""
    pb = state.get("page_briefs") or {}
    home = pb.get("home") if isinstance(pb, dict) else None
    if isinstance(home, dict):
        so = home.get("sections_outline") or []
        if so:
            return [str(x) for x in so if x]
    layout = layout_spec_from_page_briefs(state) or {}
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
    """Blocks (type + content) per section. Prefer synthetic layout from page_briefs, project_spec, site_architecture."""
    layout = layout_spec_from_page_briefs(state) or {}
    if isinstance(layout, dict):
        sections = layout.get("sections") or []
        if sections:
            blocks = []
            for s in sections:
                if not isinstance(s, dict):
                    continue
                blocks.append({
                    "type": s.get("id") or s.get("role") or "section",
                    "content": {"role": s.get("role"), "outline": True},
                })
            if blocks:
                return blocks
    spec = state.get("project_spec") or {}
    if isinstance(spec, dict) and spec.get("blocks") is not None:
        return spec.get("blocks") or []
    arch = state.get("site_architecture") or {}
    return arch.get("blocks", [])


def get_design_spec(state: dict) -> Optional[dict]:
    """Design spec (palette, typography, mood). Prefer design_tokens, then project_spec.design."""
    tokens = state.get("design_tokens") or {}
    if isinstance(tokens, dict) and (tokens.get("palette") or tokens.get("motion")):
        palette = tokens.get("palette") or {}
        key_requirements = [tokens.get("bold_design_move") or ""]
        key_requirements = [str(r) for r in key_requirements if r]
        return {
            "palette": {k: v.get("hex") if isinstance(v, dict) else str(v) for k, v in palette.items()} if isinstance(palette, dict) else {},
            "typography": "",
            "mood": str(tokens.get("bold_design_move") or ""),
            "key_requirements": key_requirements,
        }
    spec = state.get("project_spec") or {}
    if not isinstance(spec, dict):
        return None
    design = spec.get("design")
    return design if isinstance(design, dict) else None


def get_design_brief(state: dict) -> Optional[str]:
    """Full design concept for execute: guideline + page_briefs + optional design_tokens + project_spec.design_brief."""
    parts: list[str] = []
    jd = state.get("json_data")
    if isinstance(jd, dict):
        gl = jd.get("guideline")
        if isinstance(gl, str) and gl.strip():
            parts.append("=== GUIDELINE (reference) ===\n" + gl.strip()[:12000])
    pb = state.get("page_briefs")
    if isinstance(pb, dict) and pb:
        parts.append("\n=== PAGE BRIEFS ===\n" + json.dumps(pb, ensure_ascii=False, indent=2)[:16000])
    tokens = state.get("design_tokens") or {}
    if isinstance(tokens, dict) and tokens.get("palette"):
        parts.append("\n=== DESIGN TOKENS ===\n" + json.dumps(tokens, ensure_ascii=False, indent=2)[:4000])
    am = state.get("asset_manifest") or {}
    if isinstance(am, dict) and (am.get("images") or am.get("icons")):
        imgs = am.get("images") or []
        imgs = list(imgs.values()) if isinstance(imgs, dict) else (imgs if isinstance(imgs, list) else [])
        parts.append(
            "\n=== ASSET IMAGES (Unsplash) ===\n"
            + ", ".join(
                f"{i.get('role')}={i.get('url') or i.get('local_path')}"
                for i in imgs[:12]
                if isinstance(i, dict)
            )
        )
    parts.append("""
SECTION COMPOSITION — ANTI-TEMPLATE (mandatory):
- Vary layout between sections; avoid identical centered blocks everywhere.
- Each section should have one focal point; avoid generic template rhythm.
""")
    jd_has = isinstance(jd, dict) and (jd.get("guideline") or jd.get("business_requirements"))
    am_ok = bool(am.get("images") or am.get("icons"))
    if jd_has or (isinstance(pb, dict) and pb) or (
        isinstance(tokens, dict) and tokens.get("palette")
    ) or am_ok:
        return "\n".join(parts)
    spec = state.get("project_spec") or {}
    if not isinstance(spec, dict):
        return None
    brief = spec.get("design_brief")
    return (brief or "").strip() if isinstance(brief, str) else None


def get_site_target_layout_mandate(state: dict) -> str:
    """
    When site_target is mobile: mobile-first UX but layouts must scale on desktop —
    not a narrow column floating in empty space (see RESPONSIVE rules).
    When desktop: one-line hint. Empty if site_target unset.
    """
    st = (state.get("site_target") or "").strip().lower()
    if st == "mobile":
        return (
            "=== SITE TARGET: mobile-first + responsive desktop (MANDATORY) ===\n"
            "PRIMARY: Optimize for phones — narrow viewport, touch, single-column flows, "
            "tap targets ~44px min, no hover-only actions, readable type.\n"
            "DESKTOP / WIDE SCREENS: The site MUST NOT look like a thin “phone simulator” strip "
            "centered with huge empty margins. Use Tailwind breakpoints (sm: md: lg: xl:):\n"
            "- Main shell: w-full min-h-screen; expand content on md+ with max-w-6xl or max-w-7xl "
            "mx-auto px-4 lg:px-8, OR full-bleed sections with an inner constrained container.\n"
            "- Do NOT use only max-w-xs / max-w-sm (or one tiny max-width) for the entire page at "
            "all breakpoints — that causes the broken empty-sides layout on laptops.\n"
            "- Pattern: mobile = full width + padding; from md: increase max-width and spacing; "
            "Hero/blocks can be full-bleed background with inner max-w-* for text.\n"
            "=== END SITE TARGET ===\n"
        )
    if st == "desktop":
        return (
            "=== SITE TARGET: desktop-first — wide layouts and hover; still usable when the window is narrow. ===\n"
        )
    return ""


def get_spec_pipeline_mandate(state: dict) -> str:
    """
    Mandatory block from page_briefs + design_tokens: component order, palette, site target.
    Returns empty string when no page_briefs sections.
    """
    layout = layout_spec_from_page_briefs(state) or {}
    tokens = state.get("design_tokens") or {}
    if not isinstance(layout, dict) or not layout.get("sections"):
        return ""

    parts = ["=== SITE SPEC (MANDATORY — use this for generation) ==="]
    # site_target narrative lives in get_site_target_layout_mandate (execute/reasoning prepend it).

    sections = layout.get("sections", [])
    comp_names = []
    for s in sections:
        if not isinstance(s, dict):
            continue
        sid = (s.get("id") or s.get("role") or "section").strip()
        if not sid:
            continue
        comp_names.append(component_filename_from_section_key(sid))
    if comp_names:
        parts.append("COMPONENT ORDER (create .astro files in this order): " + ", ".join(comp_names))
        parts.append("In index.astro import and render home sections in this order (inner pages may use a subset).")
        pb = state.get("page_briefs") or {}
        if isinstance(pb, dict) and len(pb) > 1:
            parts.append(
                "MULTI-PAGE: create every route in generation_plan — index.astro for home plus src/pages/<slug>.astro "
                "for other ids; BaseLayout must include navigation to all routes."
            )
        parts.append(
            "Section layout: use asymmetric grids and varied composition per section — avoid identical centered blocks; "
            "one focal point per section."
        )

    if isinstance(tokens, dict) and tokens.get("palette"):
        palette = tokens.get("palette", {})
        hexes = []
        for k, v in palette.items():
            if isinstance(v, dict) and v.get("hex"):
                hexes.append(f"{k}={v['hex']}")
        if hexes:
            parts.append("PALETTE (use in Tailwind/custom.css :root or classes): " + ", ".join(hexes))

    parts.append("=== END SITE SPEC MANDATE ===\n")
    return "\n".join(parts)


def format_page_brief_for_path(state: dict, file_path: str) -> str:
    """Per-page brief from page_briefs for this src/pages/*.astro path."""
    from agents.generate_agent.spec.utils.site_pages import src_path_to_page_id

    pb = state.get("page_briefs") or {}
    if not isinstance(pb, dict) or not pb:
        return ""
    ids = [str(k) for k in pb.keys()]
    pid = src_path_to_page_id(file_path, ids)
    if not pid or pid not in pb:
        return ""
    return json.dumps(pb[pid], ensure_ascii=False, indent=2)
