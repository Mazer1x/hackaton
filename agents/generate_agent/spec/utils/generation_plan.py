"""Build ordered generation_plan (file paths) from layout_spec + canonical pages."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.generate_agent.spec.utils.site_pages import expected_page_paths


def _section_to_component_path(section: dict | Any) -> str | None:
    if not isinstance(section, dict):
        return None
    sid = (section.get("id") or section.get("role") or "").strip()
    if not sid:
        return None
    s = str(sid).strip().replace("-", " ").replace("_", " ")
    name = "".join(w.capitalize() for w in s.split()) or "Section"
    return f"src/components/{name}.astro"


def build_generation_plan(state: dict[str, Any]) -> list[str]:
    """
    Order: custom.css → BaseLayout → one component per layout_spec.sections (deduped) →
    one src/pages/*.astro per canonical page (home → index.astro).

    Falls back to Hero/About/Services if no sections when pages is multi.
    """
    plan: list[str] = ["src/styles/custom.css", "src/layouts/BaseLayout.astro"]

    layout_spec = state.get("layout_spec") or {}
    project_spec = state.get("project_spec") or {}
    sections = layout_spec.get("sections") or project_spec.get("sections") or []

    seen_comp: set[str] = set()
    if sections:
        for sec in sections:
            rel = _section_to_component_path(sec)
            if rel and rel not in seen_comp:
                seen_comp.add(rel)
                plan.append(rel)
    else:
        for name in ("Hero", "About", "Services"):
            rel = f"src/components/{name}.astro"
            if rel not in seen_comp:
                seen_comp.add(rel)
                plan.append(rel)

    canonical = state.get("canonical_spec") or {}
    page_ids = canonical.get("pages")
    if isinstance(page_ids, list) and page_ids:
        ids = [str(p).strip() for p in page_ids if str(p).strip()]
    else:
        ids = ["home"]

    for p in expected_page_paths(ids):
        if p not in plan:
            plan.append(p)

    return plan


def first_missing_plan_file(project_root: str, plan: list[str]) -> str | None:
    """First path in plan that does not exist on disk."""
    root = Path(project_root)
    for rel in plan:
        if not (root / rel).is_file():
            return rel
    return None
