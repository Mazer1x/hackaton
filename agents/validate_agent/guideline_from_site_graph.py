"""
Граф guideline_from_site: после init — **первые скриншоты** тем же механизмом, что validate
(run_screenshots / Playwright). Если в state **нет guideline** (session_export / json_data
без strategy+design), vision собирает **черновое ТЗ** (session_export) со скринов.

Не встроен в generate_agent/main автоматически — подключайте как подграф или отдельный запуск в Studio.
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

from agents.validate_agent.guideline_from_site_state import GuidelineFromSiteState
from agents.validate_agent.llm.guideline_helpers import has_guideline
from agents.validate_agent.nodes.capture_first_screenshots_node import (
    capture_first_screenshots_node,
)
from agents.validate_agent.nodes.synthesize_guideline_from_screenshots_node import (
    synthesize_guideline_from_screenshots_node,
)

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)


def prepare_guideline_route_node(state: GuidelineFromSiteState) -> dict:
    """Помечаем, было ли ТЗ до съёмки — чтобы не гонять vision зря."""
    return {"_skip_guideline_synthesis": has_guideline(state)}


def _route_after_capture(state: GuidelineFromSiteState) -> str:
    if state.get("_skip_guideline_synthesis"):
        return "end"
    return "synthesize_guideline"


print(
    "Building guideline_from_site graph: prepare → capture_first_screenshots → [synthesize | END]"
)

builder = StateGraph(GuidelineFromSiteState)
builder.add_node("prepare", prepare_guideline_route_node)
builder.add_node("capture_first_screenshots", capture_first_screenshots_node)
builder.add_node("synthesize_guideline", synthesize_guideline_from_screenshots_node)

builder.set_entry_point("prepare")
builder.add_edge("prepare", "capture_first_screenshots")
builder.add_conditional_edges(
    "capture_first_screenshots",
    _route_after_capture,
    {"end": END, "synthesize_guideline": "synthesize_guideline"},
)
builder.add_edge("synthesize_guideline", END)

graph = builder.compile()

print("guideline_from_site graph compiled.")
