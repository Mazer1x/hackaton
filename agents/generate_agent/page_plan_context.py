"""Shared multi-page route context for analyze (next missing plan file) and gather (current file)."""
from __future__ import annotations

from pathlib import Path

from agents.generate_agent.state import GenerateAgentState
from agents.generate_agent.path_case import file_exists_case_insensitive
from agents.generate_agent.spec.utils.site_pages import (
    expected_page_paths,
    src_path_to_page_id,
)


def _norm_rel(p: str) -> str:
    return p.strip().replace("\\", "/").lstrip("/")


def page_scope_updates_for_analyze(state: GenerateAgentState) -> dict:
    """
    Scope for multi-page sites (next missing generation_plan file) — applied inside analyze
    so the graph stays linear: … → analyze → reasoning (no separate page_session node).
    """
    missing = first_missing_plan_path(state)
    if not missing:
        return {
            "active_page_id": None,
            "page_plan_context": None,
            "_page_plan_missing_before": None,
        }
    return compute_page_plan_context_updates(state, missing)


def first_missing_plan_path(state: GenerateAgentState) -> str | None:
    """First path in generation_plan that does not exist on disk yet."""
    plan = state.get("generation_plan") or []
    project_path = (state.get("project_path") or "").strip()
    if not project_path or not plan:
        return None
    root = Path(project_path)
    for rel in plan:
        p = _norm_rel(str(rel))
        if not p:
            continue
        if not file_exists_case_insensitive(root, p):
            return p
    return None


def compute_page_plan_context_updates(
    state: GenerateAgentState, fp_norm: str
) -> dict:
    """
    Build active_page_id + page_plan_context for a target path (next missing file or current create_file).
    fp_norm: relative path like src/pages/about.astro or src/styles/custom.css.
    """
    fp_norm = _norm_rel(fp_norm)
    if not fp_norm:
        return {
            "active_page_id": None,
            "page_plan_context": None,
            "_page_plan_missing_before": None,
        }

    pb = state.get("page_briefs") or {}
    if isinstance(pb, dict) and pb:
        page_ids = [str(k).strip() for k in pb if str(k).strip()]
    else:
        page_ids = ["home"]

    project_path = (state.get("project_path") or "").strip()
    page_paths_ordered = expected_page_paths(page_ids)
    total_pages = len(page_paths_ordered)

    if "pages/" not in fp_norm.lower() or not fp_norm.lower().endswith(".astro"):
        if total_pages > 1:
            ctx = (
                "=== SITE PAGE PLAN (multi-page) ===\n"
                "This step is NOT a page route file — you are preparing shared assets. "
                f"Page routes to build later (in order): {', '.join(page_paths_ordered)}.\n"
                "=== END ==="
            )
            return {
                "active_page_id": None,
                "page_plan_context": ctx,
                "_page_plan_missing_before": None,
            }
        return {
            "active_page_id": None,
            "page_plan_context": None,
            "_page_plan_missing_before": None,
        }

    active_id = src_path_to_page_id(fp_norm, page_ids) or src_path_to_page_id(
        "src/pages/" + fp_norm.split("/")[-1], page_ids
    )
    if not active_id:
        active_id = page_ids[0] if page_ids else "home"

    idx_1based = 1
    target_name = Path(fp_norm).name.lower()
    for i, rel in enumerate(page_paths_ordered):
        rnorm = _norm_rel(rel)
        if rnorm == fp_norm or Path(rnorm).name.lower() == target_name:
            idx_1based = i + 1
            break

    missing_before: list[str] = []
    root = Path(project_path) if project_path else None
    cur_index = idx_1based - 1
    if root and cur_index > 0:
        for j in range(cur_index):
            rel = page_paths_ordered[j]
            if not file_exists_case_insensitive(root, rel):
                missing_before.append(rel)

    lines = [
        f"=== PAGE GENERATION (multi-page site): route {idx_1based} of {total_pages} ===",
        f"Active page id: {active_id}",
        f"Ordered page files: {' → '.join(page_paths_ordered)}",
        f"Current file targets this route: {fp_norm}",
    ]
    if total_pages > 1:
        lines.append(
            "When writing this .astro file: treat it as ONE route of the site; BaseLayout + nav must "
            "link all routes; content and sections must match page_briefs for this page_id."
        )
    if missing_before:
        lines.append(
            "WARNING — earlier routes in plan are not on disk yet: "
            + ", ".join(missing_before)
            + ". If the product owner requires strict order, complete those first."
        )
    lines.append("=== END PAGE PLAN ===")
    page_plan_context = "\n".join(lines)

    return {
        "active_page_id": active_id,
        "page_plan_context": page_plan_context,
        "_page_plan_missing_before": missing_before or None,
    }
