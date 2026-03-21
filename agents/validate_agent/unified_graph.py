"""
Unified graph: generate_agent → validate_agent.

Один скомпилированный граф LangGraph: ноды `generate` и `validate` — встроенные подграфы
(тот же compiled graph, что в generate_agent/main и validate_agent/main), общий UnifiedState.
"""
from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from agents.validate_agent.unified_state import UnifiedState
from agents.generate_agent.main import graph as generate_graph
from agents.validate_agent.main import graph as validate_graph

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)


print("Building unified graph (generate subgraph → validate subgraph → END)...")

builder = StateGraph(UnifiedState)
builder.add_node("generate", generate_graph)
builder.add_node("validate", validate_graph)
builder.set_entry_point("generate")
builder.add_edge("generate", "validate")
builder.add_edge("validate", END)

graph = builder.compile()

print("Unified graph compiled successfully!")
print("   Flow: generate (embedded subgraph) → validate (embedded subgraph) → END")
