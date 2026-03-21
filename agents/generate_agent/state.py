# state.py
from typing import Annotated, Optional

try:
    from typing_extensions import TypedDict
except ImportError:
    from typing import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def _merge_project_path(left: Optional[str], right: Optional[str]) -> Optional[str]:
    """Last-wins merge: fork (init_project) + Studio input can both set project_path in one step."""
    if right is not None:
        return right
    return left


class GenerateAgentState(TypedDict):
    """Agent state: list of messages (including tool_calls and tool results)."""
    messages: Annotated[list[BaseMessage], add_messages]
    
    # Context for autonomous work
    requirements: Optional[dict]  # Site requirements (style, features, colors)
    design_tokens: Optional[dict]  # Design system (colors, fonts, spacing)
    files_created: list[str]  # List of created files
    project_path: Annotated[Optional[str], _merge_project_path]  # Path to project
    iteration_count: int  # Iteration counter (for debugging)
    
    # Content from Structure Agent / JSON (so generated site uses real data, not placeholders)
    json_data: Optional[dict]  # Raw JSON brief (brand, business, site_goals, etc.) — fallback when no project_spec
    session_export: Optional[dict]  # SessionExport (strategy, design, rkn) — set by prepare_spec_input; consumed by llm_design_requirements
    site_target: Optional[str]  # "mobile" | "desktop" — from json_data.site_target; mobile-first vs desktop-first UX
    site_architecture: Optional[dict]  # From structure_agent: sections, blocks, navigation — fallback when no project_spec
    site_info: Optional[str]  # Short summary (theme, brand, CTA) for reasoning/load_skills; full brief only in execute

    # ТЗ from planning subgraph (primary source when set). Structure: short_summary, content_brief, sections, blocks
    project_spec: Optional[dict]

    # Phase 1 (before global design): per-page briefs from ТЗ — page_briefs_node → page_briefs[page_id]
    page_briefs: Optional[dict]

    # Multi-page: analyze merges scope from next missing plan file; gather refreshes from reasoning file_path
    active_page_id: Optional[str]  # logical page id when current step is src/pages/*.astro
    page_plan_context: Optional[str]  # human-readable block: "page 2 of 5", ordered routes, warnings
    _page_plan_missing_before: Optional[list]  # earlier page files missing on disk (optional warning)

    # Spec pipeline: canonical_spec (semantic) + llm_design_requirements → brand_profile, design_tokens,
    # typography_spec, layout_spec, background_spec, animation_spec; unsplash_search → asset_manifest
    canonical_spec: Optional[dict]
    brand_profile: Optional[dict]
    typography_spec: Optional[dict]
    layout_spec: Optional[dict]
    background_spec: Optional[dict]
    asset_manifest: Optional[dict]
    animation_spec: Optional[dict]
    
    # Multi-model reasoning
    reasoning_decision: Optional[dict]  # Reasoning model decision (what to do next)
    # Structure: {"action": "create_file", "target": "Hero.astro", "reasoning": "...", "done": False}
    
    # Explicit context from load_skills (skills + read_file results) for execute
    loaded_skills_context: Optional[str]  # Filled by prepare_context node; execute uses this in prompt
    # Design context for current step only (from spec pipeline), filled by summarize_design_for_step before execute
    step_design_summary: Optional[str]
    
    # Project analysis
    project_analysis: Optional[dict]  # Project structure analysis (what files exist)
    # Structure: {"status": "needs_components", "message": "...", "src_structure": {...}}

    # Generation plan: list of file paths to create; plan_status = which exist (physical check, no AI)
    generation_plan: Optional[list[str]]  # Ordered paths: styles → layout → components → src/pages/*.astro (multi-page = several page files)
    plan_status: Optional[dict]  # path -> bool (exists). Set by check_plan node.

    # Deployment / git
    site_url: Optional[str]  # Продакшен URL без порта: https://automatoria.ru/{repo}/ (для скринов/валидации после unified)
    repo_name: Optional[str]  # Имя репозитория на git-сервере (по умолчанию basename project_path)
    deploy_log: Optional[str]  # Полный лог git init/add/commit/push
    deploy_url: Optional[str]  # DEPLOY_URL из вывода post-receive hook (если есть)

    # Join flags: init and spec pipeline run in parallel, sync runs until both are set
    _init_done: Optional[bool]
    _spec_done: Optional[bool]

    # After reasoning: check if target file already exists (skip execute, re-analyze and re-reason)
    _step_file_existed: Optional[bool]  # True = file exists → go to analyze; False → gather_context
    file_already_created_path: Optional[str]  # Path that was skipped (reasoning uses to pick next or complete)

    # Цикл verify ↔ fix_index (после complete)
    _index_import_fix_rounds: Optional[int]
    _verify_after_fix: Optional[bool]
