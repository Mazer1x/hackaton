"""Build ordered generation_plan (file paths) from page_briefs + project_spec."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agents.generate_agent.component_naming import component_filename_from_section_key
from agents.generate_agent.path_case import file_exists_case_insensitive
from agents.generate_agent.spec.utils.site_pages import expected_page_paths


def _section_to_component_path(section: dict | Any) -> str | None:
    if not isinstance(section, dict):
        return None
    sid = (section.get("id") or section.get("role") or "").strip()
    if not sid:
        return None
    fn = component_filename_from_section_key(sid)
    return f"src/components/{fn}"


def _sections_from_page_briefs(pb: dict[str, Any]) -> list[dict[str, Any]]:
    """Union section ids from sections_outline (home first, then other pages)."""
    seen: set[str] = set()
    sections: list[dict[str, Any]] = []
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
    return sections


def build_generation_plan(state: dict[str, Any]) -> list[str]:
    """
    Order: custom.css → BaseLayout → one component per section (from page_briefs) →
    one src/pages/*.astro per page id in page_briefs.
    """
    plan: list[str] = ["src/styles/custom.css", "src/layouts/BaseLayout.astro"]

    project_spec = state.get("project_spec") or {}
    pb = state.get("page_briefs") or {}
    sections = (project_spec.get("sections") or []) if isinstance(project_spec, dict) else []
    if not sections and isinstance(pb, dict) and pb:
        sections = _sections_from_page_briefs(pb)

    seen_comp: set[str] = set()
    if sections:
        for sec in sections:
            rel = _section_to_component_path(sec if isinstance(sec, dict) else {"id": str(sec)})
            if rel and rel not in seen_comp:
                seen_comp.add(rel)
                plan.append(rel)
    else:
        for name in ("Hero", "About", "Services"):
            rel = f"src/components/{name}.astro"
            if rel not in seen_comp:
                seen_comp.add(rel)
                plan.append(rel)

    if isinstance(pb, dict) and pb:
        ids = [str(k).strip() for k in pb if str(k).strip()]
    else:
        ids = ["home"]

    for p in expected_page_paths(ids):
        if p not in plan:
            plan.append(p)

    return plan


def first_missing_plan_file(project_root: str, plan: list[str]) -> str | None:
    """First path in plan that does not exist on disk (case-insensitive)."""
    root = Path(project_root)
    for rel in plan:
        if not file_exists_case_insensitive(root, rel):
            return rel
    return None
