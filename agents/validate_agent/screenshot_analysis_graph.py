"""
Граф: снятие скриншотов → загрузка на сервер → анализ через vision-модель.
Вход: project_path или site_url, опционально repo_name, deploy_url, site_info, json_data, project_spec.
Выход: screenshot_dir, screenshot_paths, screenshot_urls, screenshot_message, validation_result.
"""
from pathlib import Path
from typing import Annotated, Optional

try:
    from typing_extensions import TypedDict
except ImportError:
    from typing import TypedDict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from agents.generate_agent.state import _merge_project_path
from agents.validate_agent.nodes.run_screenshots_node import _run_screenshots_node
from agents.validate_agent.nodes.upload_screenshots_node import _upload_screenshots_node
from agents.validate_agent.nodes.analyze_screenshots_node import _analyze_screenshots_node

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)


class ScreenshotAnalysisState(TypedDict, total=False):
    """State графа: снятие скриншотов → загрузка → анализ."""
    project_path: Annotated[Optional[str], _merge_project_path]
    site_url: Optional[str]
    repo_name: Optional[str]
    deploy_url: Optional[str]
    screenshot_dir: Optional[str]
    screenshot_paths: list
    screenshot_urls: list
    screenshot_page_urls: Optional[list]
    screenshot_message: Optional[str]
    site_info: Optional[str]
    site_target: Optional[str]
    json_data: Optional[dict]
    project_spec: Optional[dict]
    page_briefs: Optional[dict]
    generation_plan: Optional[list]
    design_tokens: Optional[dict]
    validation_result: Optional[dict]


builder = StateGraph(ScreenshotAnalysisState)
builder.add_node("run_screenshots", _run_screenshots_node)
builder.add_node("upload_screenshots", _upload_screenshots_node)
builder.add_node("analyze_screenshots", _analyze_screenshots_node)
builder.set_entry_point("run_screenshots")
builder.add_edge("run_screenshots", "upload_screenshots")
builder.add_edge("upload_screenshots", "analyze_screenshots")
builder.add_edge("analyze_screenshots", END)

screenshot_analysis_graph = builder.compile()
