# guideline_from_site_state.py
"""State для графа guideline_from_site (скрины → synthetic session_export)."""
from __future__ import annotations

from typing import Annotated, Optional

try:
    from typing_extensions import TypedDict
except ImportError:
    from typing import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from agents.generate_agent.state import _merge_project_path


class GuidelineFromSiteState(TypedDict, total=False):
    """Совместим с generate/unified: project_path, json_data/session_export, скрины."""

    messages: Annotated[list[BaseMessage], add_messages]

    project_path: Annotated[Optional[str], _merge_project_path]
    site_url: Optional[str]
    deploy_url: Optional[str]
    repo_name: Optional[str]
    json_data: Optional[dict]
    session_export: Optional[dict]
    site_target: Optional[str]
    site_info: Optional[str]
    generation_plan: Optional[list[str]]

    screenshot_dir: Optional[str]
    screenshot_paths: list[str]
    screenshot_message: Optional[str]
    validation_result: Optional[dict]

    _skip_guideline_synthesis: Optional[bool]
    guideline_source: Optional[str]
    guideline_synthesis_error: Optional[str]
    guideline_synthesis_raw: Optional[str]
