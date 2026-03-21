# nodes/summarize_design_for_step_node.py
"""
Summarize Design For Step Node — runs after prepare_context, before execute.
Collects output from design nodes (spec pipeline: canonical_spec, brand_profile, design_tokens,
typography_spec, layout_spec, background_spec, animation_spec) and returns a short summary
relevant only for the current file (from reasoning_decision.file_path).
No LLM: rule-based extraction and formatting.
"""
import json
from pathlib import Path

from agents.generate_agent.state import GenerateAgentState
from agents.generate_agent.utils import get_content_brief, get_spec_blocks, get_spec_sections, format_page_brief_for_path


def _file_kind(file_path: str) -> tuple[str, str]:
    """Return (kind, section_id). kind: 'css' | 'layout' | 'component' | 'page'."""
    p = (file_path or "").strip().lower().replace("\\", "/")
    if not p:
        return "css", ""
    if "custom.css" in p or "styles/" in p and p.endswith(".css"):
        return "css", ""
    if "layouts/" in p and p.endswith(".astro"):
        return "layout", ""
    if "pages/" in p and ("index" in p or p.endswith(".astro")):
        return "page", ""
    if "components/" in p and p.endswith(".astro"):
        name = Path(p).stem
        section_id = name.lower().replace("-", "_")
        return "component", section_id
    return "css", ""


def _build_css_summary(state: GenerateAgentState) -> str:
    tokens = state.get("design_tokens") or {}
    typo = state.get("typography_spec") or {}
    animation = state.get("animation_spec") or {}
    parts = ["DESIGN CONTEXT FOR custom.css (from spec pipeline)\n"]

    if isinstance(tokens, dict):
        if tokens.get("palette"):
            parts.append("PALETTE (use in :root, exact hex):")
            for k, v in (tokens.get("palette") or {}).items():
                if isinstance(v, dict) and v.get("hex"):
                    parts.append(f"  --{k}: {v['hex']};")
        if tokens.get("bold_design_move"):
            parts.append("Bold design move: " + str(tokens.get("bold_design_move")))
        if tokens.get("bold_design_move_implementation"):
            parts.append("Implementation: " + str(tokens.get("bold_design_move_implementation"))[:500])
        if tokens.get("motion"):
            parts.append("Motion: " + json.dumps(tokens.get("motion"), ensure_ascii=False)[:400])
        if tokens.get("spacing_scale"):
            parts.append("Spacing scale: " + str(tokens.get("spacing_scale"))[:200])
        if tokens.get("border_radius"):
            parts.append("Border radius: " + str(tokens.get("border_radius"))[:200])

    if isinstance(typo, dict):
        for key in ("primary", "secondary"):
            f = typo.get(key)
            if isinstance(f, dict) and f.get("family"):
                parts.append(f"Font {key}: {f.get('family')} weights {f.get('weights', [])}")
        urls = typo.get("font_import_urls") or []
        if isinstance(urls, dict):
            urls = list(urls.values())
        if urls:
            parts.append("Font import URLs (use in layout): " + ", ".join(str(u) for u in urls[:5]))

    if isinstance(animation, dict) and animation.get("global"):
        g = animation.get("global") or {}
        if g.get("reduced_motion_strategy"):
            parts.append("Reduced motion: " + str(g.get("reduced_motion_strategy"))[:200])

    return "\n".join(parts) if len(parts) > 1 else ""


def _build_layout_summary(state: GenerateAgentState) -> str:
    layout = state.get("layout_spec") or {}
    typo = state.get("typography_spec") or {}
    tokens = state.get("design_tokens") or {}
    canonical = state.get("canonical_spec") or {}
    parts = ["DESIGN CONTEXT FOR BaseLayout.astro\n"]

    if isinstance(layout, dict) and layout.get("sections"):
        comp_order = []
        for s in layout.get("sections", []):
            if isinstance(s, dict):
                sid = s.get("id") or s.get("role") or "section"
                name = str(sid).replace("_", " ").title().replace(" ", "") + ".astro"
                comp_order.append(name)
        if comp_order:
            parts.append("Component order (for index): " + ", ".join(comp_order))
        if layout.get("ascii_wireframe"):
            parts.append("Wireframe (structure): " + (layout.get("ascii_wireframe") or "")[:1500])

    if isinstance(typo, dict):
        urls = typo.get("font_import_urls") or []
        if isinstance(urls, dict):
            urls = list(urls.values())
        if urls:
            parts.append("Add to <head>: " + " ".join(f'<link href="{u}" rel="stylesheet">' for u in urls[:5]))

    if isinstance(tokens, dict) and tokens.get("palette"):
        parts.append("Import custom.css for palette and variables.")

    if isinstance(canonical, dict) and canonical.get("primary_cta"):
        cta = canonical["primary_cta"]
        if isinstance(cta, dict):
            parts.append(f"Primary CTA: {cta.get('label')} -> {cta.get('link')}")

    return "\n".join(parts) if len(parts) > 1 else ""


def _find_section(layout_spec: dict, section_id: str) -> dict | None:
    sections = layout_spec.get("sections") or []
    for s in sections:
        if not isinstance(s, dict):
            continue
        sid = (s.get("id") or s.get("role") or "").strip().lower().replace("-", "_")
        if sid == section_id:
            return s
    return None


def _build_component_summary(state: GenerateAgentState, section_id: str) -> str:
    layout = state.get("layout_spec") or {}
    background = state.get("background_spec") or {}
    animation = state.get("animation_spec") or {}
    tokens = state.get("design_tokens") or {}
    typo = state.get("typography_spec") or {}
    blocks = get_spec_blocks(state)
    content_brief = get_content_brief(state)

    parts = [f"DESIGN CONTEXT FOR {section_id} section (this component only)\n"]

    section = _find_section(layout, section_id) if isinstance(layout, dict) else None
    if section:
        parts.append("Layout: grid=" + str(section.get("grid", "")) + ", role=" + str(section.get("role", "")))
        if section.get("background_layer"):
            parts.append("Background layer: " + str(section.get("background_layer")))
        if section.get("elements"):
            parts.append("Elements: " + json.dumps(section.get("elements", []), ensure_ascii=False)[:400])
        role = section.get("role") or section_id
        if "★" in str(section.get("id", "")) or "★" in str(role):
            parts.append("This section is the BOLD DESIGN MOVE — make it visually dominant.")

    bgs = (background.get("backgrounds") or {}) if isinstance(background, dict) else {}
    if isinstance(bgs, dict):
        bg = bgs.get(section_id) or bgs.get(section_id.replace("_", ""))
        if isinstance(bg, dict):
            parts.append("Background: type=" + str(bg.get("background_type")) + ", config=" + str(bg.get("config"))[:300])
    elif isinstance(bgs, list):
        for bg in bgs:
            if isinstance(bg, dict) and (bg.get("section_id") or "").strip().lower().replace("-", "_") == section_id:
                parts.append("Background: " + json.dumps(bg, ensure_ascii=False)[:400])
                break

    anim_sections = (animation.get("sections") or {}) if isinstance(animation, dict) else {}
    if isinstance(anim_sections, dict):
        anim = anim_sections.get(section_id) or anim_sections.get(section_id.replace("_", ""))
        if isinstance(anim, dict):
            parts.append("Animation: entrance=" + str(anim.get("entrance")) + ", hover=" + str(anim.get("hover"))[:200])
    elif isinstance(anim_sections, list):
        for a in anim_sections:
            if isinstance(a, dict) and (a.get("section_id") or "").strip().lower().replace("-", "_") == section_id:
                parts.append("Animation: " + json.dumps(a, ensure_ascii=False)[:300])
                break

    for b in (blocks or []):
        if isinstance(b, dict) and (b.get("type") or "").strip().lower().replace("-", "_") == section_id:
            parts.append("Block content: " + json.dumps(b.get("content", {}), ensure_ascii=False)[:500])
            break

    if content_brief and section_id == "hero":
        parts.append("Content (hero): " + content_brief[:600])

    if isinstance(tokens, dict) and tokens.get("palette"):
        hexes = [f"{k}={v.get('hex')}" for k, v in (tokens.get("palette") or {}).items() if isinstance(v, dict) and v.get("hex")]
        if hexes:
            parts.append("Use palette: " + ", ".join(hexes[:6]))
    if isinstance(typo, dict) and (typo.get("primary") or typo.get("secondary")):
        p = (typo.get("primary") or {}).get("family") if isinstance(typo.get("primary"), dict) else None
        s = (typo.get("secondary") or {}).get("family") if isinstance(typo.get("secondary"), dict) else None
        if p or s:
            parts.append("Typography: heading=" + (p or "—") + ", body=" + (s or "—"))

    return "\n".join(parts) if len(parts) > 1 else ""


def _build_page_summary(state: GenerateAgentState, rel_path: str) -> str:
    layout = state.get("layout_spec") or {}
    canonical = state.get("canonical_spec") or {}
    page_name = Path(rel_path).name if rel_path else "index.astro"
    ppc = (state.get("page_plan_context") or "").strip()
    parts = []
    if ppc:
        parts.append(ppc + "\n")
    parts.append(f"DESIGN CONTEXT FOR {page_name} (Astro page)\n")
    if page_name.lower() != "index.astro":
        parts.append(
            "Inner route: use BaseLayout; include site nav with links to all routes from the brief; "
            "only import components needed for this page (not necessarily the full home stack).\n"
        )

    pb_one = format_page_brief_for_path(state, rel_path)
    if pb_one:
        parts.append("PAGE BRIEF (Phase 1, this route):\n" + pb_one)

    if isinstance(layout, dict) and layout.get("sections"):
        comp_order = []
        for s in layout.get("sections", []):
            if isinstance(s, dict):
                sid = s.get("id") or s.get("role") or "section"
                name = str(sid).replace("_", " ").title().replace(" ", "")
                comp_order.append(f"import {name} from '../components/{name}.astro'")
        if comp_order:
            parts.append("Import and render in this order:\n" + "\n".join(comp_order))
        parts.append("Use BaseLayout; pass no props. Sections order must match layout_spec.")

    if isinstance(canonical, dict) and canonical.get("primary_cta"):
        cta = canonical["primary_cta"]
        if isinstance(cta, dict):
            parts.append(f"CTA in layout: {cta.get('label')} -> {cta.get('link')}")

    return "\n".join(parts) if len(parts) > 1 else ""


def _summarize_design_for_step_node(state: GenerateAgentState) -> dict:
    """
    Build a short design summary from spec pipeline outputs, relevant only for the file
    in reasoning_decision.file_path. Returns step_design_summary (or empty if no decision).
    """
    decision = state.get("reasoning_decision") or {}
    if decision.get("action") != "create_file":
        return {"step_design_summary": None}

    file_path = (decision.get("file_path") or "").strip().lstrip("/")
    if not file_path:
        return {"step_design_summary": None}

    kind, section_id = _file_kind(file_path)

    if kind == "css":
        summary = _build_css_summary(state)
    elif kind == "layout":
        summary = _build_layout_summary(state)
    elif kind == "component" and section_id:
        summary = _build_component_summary(state, section_id)
    elif kind == "page":
        summary = _build_page_summary(state, file_path)
    else:
        summary = _build_css_summary(state)

    if not summary.strip():
        return {"step_design_summary": None}

    return {"step_design_summary": f"=== DESIGN CONTEXT FOR THIS FILE (from spec pipeline) ===\n{summary}\n=== END ===\n"}
