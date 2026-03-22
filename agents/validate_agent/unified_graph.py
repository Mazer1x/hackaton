"""
Unified graph: generate_agent → handoff → validate_agent.

Один скомпилированный граф LangGraph: `generate` и `validate` — те же compiled subgraph,
общий UnifiedState: после генерации в validate попадают json_data, page_briefs, design_tokens,
generation_plan, project_path, repo_name и т.д.; нода handoff сбрасывает только скрины/validation_result.
"""
from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from agents.validate_agent.unified_state import UnifiedState
from agents.generate_agent.main import graph as generate_graph
from agents.validate_agent.main import graph as validate_graph
from agents.validate_agent.nodes.unified_handoff_node import unified_handoff_to_validate_node

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)


print("Building unified graph (generate → handoff → validate → END)...")

builder = StateGraph(UnifiedState)
builder.add_node("generate", generate_graph)
builder.add_node("handoff_to_validate", unified_handoff_to_validate_node)
builder.add_node("validate", validate_graph)
builder.set_entry_point("generate")
builder.add_edge("generate", "handoff_to_validate")
builder.add_edge("handoff_to_validate", "validate")
builder.add_edge("validate", END)

graph = builder.compile()

print("Unified graph compiled successfully!")
print(
    "   Flow: generate (spec, page_briefs, design_tokens, код) → handoff (сброс screenshot_*) → "
    "validate (normalize → deploy → скрины по page_brief + design_tokens → …) → END"
)
