# nodes/summarize_design_for_step_node.py
"""
Summarize Design For Step Node — runs after prepare_context, before execute.
Uses page_briefs, guideline bundle (json_data), and design_tokens for the current file.
No LLM: rule-based extraction.
"""
import json
from pathlib import Path

from agents.generate_agent.state import GenerateAgentState
from agents.generate_agent.component_naming import pascal_case_component_basename
from agents.generate_agent.utils import (
    format_page_brief_for_path,
    get_content_brief,
    get_site_target_layout_mandate,
    layout_spec_from_page_briefs,
)


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
    parts = ["DESIGN CONTEXT FOR custom.css\n"]

    if isinstance(tokens, dict):
        if tokens.get("palette"):
            parts.append("PALETTE (use in :root, exact hex):")
            for k, v in (tokens.get("palette") or {}).items():
                if isinstance(v, dict) and v.get("hex"):
                    parts.append(f"  --{k}: {v['hex']};")
        if tokens.get("bold_design_move"):
            parts.append("Bold design move: " + str(tokens.get("bold_design_move")))
        if tokens.get("motion"):
            parts.append("Motion: " + json.dumps(tokens.get("motion"), ensure_ascii=False)[:400])

    return "\n".join(parts) if len(parts) > 1 else ""


def _build_layout_summary(state: GenerateAgentState) -> str:
    parts = ["DESIGN CONTEXT FOR BaseLayout.astro\n"]
    st = state.get("site_target")
    if st:
        parts.append(f"site_target: {st}")
    st_mandate = get_site_target_layout_mandate(state)
    if st_mandate.strip():
        parts.append(st_mandate.strip())
    jd = state.get("json_data")
    if isinstance(jd, dict) and isinstance(jd.get("guideline"), str) and jd["guideline"].strip():
        parts.append("Guideline excerpt: " + jd["guideline"].strip()[:1200])
    return "\n".join(parts) if len(parts) > 1 else ""


def _outline_has_section(state: GenerateAgentState, section_id: str) -> bool:
    sid = section_id.replace("-", "_").lower()
    pb = state.get("page_briefs") or {}
    if not isinstance(pb, dict):
        return False
    for pdata in pb.values():
        if not isinstance(pdata, dict):
            continue
        for name in pdata.get("sections_outline") or []:
            if not isinstance(name, str):
                continue
            if name.strip().lower().replace(" ", "_") == sid:
                return True
    return False


def _build_component_summary(state: GenerateAgentState, section_id: str) -> str:
    tokens = state.get("design_tokens") or {}
    content_brief = get_content_brief(state)
    parts = [f"DESIGN CONTEXT FOR {section_id} section (this component only)\n"]

    if _outline_has_section(state, section_id):
        parts.append("This section is listed in page_briefs.sections_outline — follow that outline and design_notes.")

    if content_brief and section_id in ("hero", "home"):
        parts.append("Content: " + content_brief[:600])

    if isinstance(tokens, dict) and tokens.get("palette"):
        hexes = [f"{k}={v.get('hex')}" for k, v in (tokens.get("palette") or {}).items() if isinstance(v, dict) and v.get("hex")]
        if hexes:
            parts.append("Use palette: " + ", ".join(hexes[:6]))

    return "\n".join(parts) if len(parts) > 1 else ""


def _build_page_summary(state: GenerateAgentState, rel_path: str) -> str:
    page_name = Path(rel_path).name if rel_path else "index.astro"
    ppc = (state.get("page_plan_context") or "").strip()
    parts = []
    if ppc:
        parts.append(ppc + "\n")
    parts.append(f"DESIGN CONTEXT FOR {page_name} (Astro page)\n")
    if page_name.lower() != "index.astro":
        parts.append(
            "Inner route: use BaseLayout; include site nav with links to all routes from page_briefs; "
            "only import components needed for this page.\n"
        )

    pb_one = format_page_brief_for_path(state, rel_path)
    if pb_one:
        parts.append("PAGE BRIEF (this route):\n" + pb_one)

    layout = layout_spec_from_page_briefs(state) or {}
    if isinstance(layout, dict) and layout.get("sections"):
        comp_order = []
        for s in layout.get("sections", []):
            if isinstance(s, dict):
                sid = s.get("id") or s.get("role") or "section"
                name = pascal_case_component_basename(str(sid))
                comp_order.append(f"import {name} from '../components/{name}.astro'")
        if comp_order:
            parts.append("Import and render in this order:\n" + "\n".join(comp_order))

    return "\n".join(parts) if len(parts) > 1 else ""


def _summarize_design_for_step_node(state: GenerateAgentState) -> dict:
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

    return {"step_design_summary": f"=== DESIGN CONTEXT FOR THIS FILE ===\n{summary}\n=== END ===\n"}

