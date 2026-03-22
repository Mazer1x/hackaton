# state.py
from typing import Annotated, Optional

try:
    from typing_extensions import TypedDict
except ImportError:
    from typing import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def _merge_project_path(left: Optional[str], right: Optional[str]) -> Optional[str]:
    """Last-wins merge: init_project + Studio input can both set project_path in one step."""
    if right is not None:
        return right
    return left


class GenerateAgentState(TypedDict):
    """Agent state: list of messages (including tool_calls and tool results)."""
    messages: Annotated[list[BaseMessage], add_messages]
    
    # Context for autonomous work
    requirements: Optional[dict]  # Site requirements (style, features, colors)
    design_tokens: Optional[dict]  # Design system (colors, fonts, spacing)
    # Reference site (validate run_screenshots → upload_screenshots → vision), optional
    design_reference_url: Optional[str]
    reference_screenshot_dir: Optional[str]
    reference_screenshot_paths: Optional[list[str]]
    reference_screenshot_urls: Optional[list[str]]
    reference_design_message: Optional[str]
    reference_design_source: Optional[str]
    reference_design_error: Optional[str]
    reference_design_raw: Optional[str]
    files_created: list[str]  # List of created files
    project_path: Annotated[Optional[str], _merge_project_path]  # Path to project
    iteration_count: int  # Iteration counter (for debugging)
    
    # Content from Structure Agent / JSON (so generated site uses real data, not placeholders)
    # json_data.design_preferences: опционально — явные визуальные преференсы; LLM → design_tokens до reference-сайта
    json_data: Optional[dict]  # Guideline bundle: guideline, business_requirements, user_preferences, design_preferences
    site_target: Optional[str]  # "mobile" | "desktop" — from json_data / user_preferences
    site_architecture: Optional[dict]  # From structure_agent: sections, blocks, navigation — fallback when no project_spec
    site_info: Optional[str]  # Short summary (theme, brand, CTA) for reasoning/load_skills; full brief only in execute

    # ТЗ from planning subgraph (primary source when set). Structure: short_summary, content_brief, sections, blocks
    project_spec: Optional[dict]

    # Phase 1: per-page briefs from guideline bundle — page_briefs_node → page_briefs[page_id]
    page_briefs: Optional[dict]
    asset_manifest: Optional[dict]  # unsplash_search: images[], icons[]

    # Multi-page: analyze merges scope from next missing plan file; gather refreshes from reasoning file_path
    active_page_id: Optional[str]  # logical page id when current step is src/pages/*.astro
    page_plan_context: Optional[str]  # human-readable block: "page 2 of 5", ordered routes, warnings
    _page_plan_missing_before: Optional[list]  # earlier page files missing on disk (optional warning)

    # Multi-model reasoning
    reasoning_decision: Optional[dict]  # Reasoning model decision (what to do next)
    # Structure: {"action": "create_file", "target": "Hero.astro", "reasoning": "...", "done": False}
    
    # Explicit context from load_skills (skills + read_file results) for execute
    loaded_skills_context: Optional[str]  # Filled by prepare_context node; execute uses this in prompt
    # Design context for current step (page_briefs + tokens), filled by summarize_design_for_step before execute
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

    # Informational: init_project / spec_finalize (линейный граф; для отладки и Studio)
    _init_done: Optional[bool]
    _spec_done: Optional[bool]

    # After reasoning: check if target file already exists (skip execute, re-analyze and re-reason)
    _step_file_existed: Optional[bool]  # True = file exists → go to analyze; False → gather_context
    file_already_created_path: Optional[str]  # Path that was skipped (reasoning uses to pick next or complete)

    # Цикл verify ↔ fix_index (после complete)
    _index_import_fix_rounds: Optional[int]
    _verify_after_fix: Optional[bool]
