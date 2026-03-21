"""
Tools for the reasoning node: structured decision output.
The model calls one of these instead of returning free-form JSON; we map tool_calls to reasoning_decision.
"""
from typing import Optional

from langchain_core.tools import BaseTool, tool


@tool
def create_file_step(
    file_path: str,
    file_type: str,
    purpose: str,
    reasoning: str,
    key_requirements: Optional[list[str]] = None,
    recommended_skill: Optional[str] = None,
) -> str:
    """Decide to create a file in this step. Call this when project_analysis.status is NOT 'complete'.
    Order: custom.css → BaseLayout.astro → components (Hero, About, etc.) → page(s): index.astro and other src/pages/*.astro for multi-page sites.
    file_path: relative path e.g. src/styles/custom.css, src/layouts/BaseLayout.astro, src/components/Hero.astro, src/pages/schedule.astro.
    file_type: css | layout | astro_component | page.
    purpose: short description of what this file is for.
    reasoning: why this file next.
    key_requirements: list of design/implementation requirements (e.g. '5+ @keyframes', 'bold typography').
    recommended_skill: optional, e.g. frontend-design or astro-expert."""
    return "OK: create_file decision recorded."


@tool
def complete_step(reasoning: str) -> str:
    """Decide the project is complete. Call ONLY when project_analysis.status is 'complete' (all files exist)."""
    return "OK: complete decision recorded."


def get_reasoning_decision_tools() -> list[BaseTool]:
    """Tools for reasoning node: structured create_file or complete decision."""
    return [create_file_step, complete_step]
