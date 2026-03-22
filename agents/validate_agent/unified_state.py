# unified_state.py
"""
Unified state for generate → validate graph (раньше в agents.unified_agent.state).
Объединяет поля GenerateAgentState и ValidateAgentState.
"""
from typing import Annotated, Optional

try:
    from typing_extensions import TypedDict
except ImportError:
    from typing import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from agents.generate_agent.state import _merge_project_path


class UnifiedState(TypedDict, total=False):
    """State for generate→validate: all fields from both agents preserved in one graph."""

    messages: Annotated[list[BaseMessage], add_messages]

    project_path: Annotated[Optional[str], _merge_project_path]
    site_url: Optional[str]
    headless: Optional[bool]
    json_data: Optional[dict]
    project_spec: Optional[dict]
    requirements: Optional[dict]
    design_tokens: Optional[dict]
    # Reference site (generate: run_reference_screenshots → … → synthesize_reference_design)
    design_reference_url: Optional[str]
    reference_screenshot_dir: Optional[str]
    reference_screenshot_paths: Optional[list[str]]
    reference_screenshot_urls: Optional[list[str]]
    reference_design_message: Optional[str]
    reference_design_source: Optional[str]
    reference_design_error: Optional[str]
    reference_design_raw: Optional[str]
    session_export: Optional[dict]
    site_architecture: Optional[dict]
    site_target: Optional[str]
    site_info: Optional[str]
    canonical_spec: Optional[dict]
    page_briefs: Optional[dict]
    active_page_id: Optional[str]
    page_plan_context: Optional[str]
    _page_plan_missing_before: Optional[list]
    brand_profile: Optional[dict]
    typography_spec: Optional[dict]
    layout_spec: Optional[dict]
    background_spec: Optional[dict]
    asset_manifest: Optional[dict]
    animation_spec: Optional[dict]

    files_created: list[str]
    iteration_count: int
    reasoning_decision: Optional[dict]
    loaded_skills_context: Optional[str]
    step_design_summary: Optional[str]
    project_analysis: Optional[dict]
    generation_plan: Optional[list[str]]
    plan_status: Optional[dict]
    _init_done: Optional[bool]
    _spec_done: Optional[bool]
    _step_file_existed: Optional[bool]
    file_already_created_path: Optional[str]
    _index_import_fix_rounds: Optional[int]
    _verify_after_fix: Optional[bool]

    repo_name: Optional[str]
    deploy_log: Optional[str]
    deploy_url: Optional[str]

    validation_result: Optional[dict]
    edit_research_notes: Optional[str]

    # guideline_from_site subgraph
    _skip_guideline_synthesis: Optional[bool]
    guideline_source: Optional[str]
    guideline_synthesis_error: Optional[str]
    guideline_synthesis_raw: Optional[str]

    screenshot_dir: Optional[str]
    screenshot_paths: list[str]
    screenshot_message: Optional[str]
    screenshot_urls: list[str]
    screenshot_page_urls: Optional[list[list[str]]]
    fix_attempts: Optional[int]
    rag_indexed: Optional[bool]
    rag_chunks_count: Optional[int]
    rag_message: Optional[str]
