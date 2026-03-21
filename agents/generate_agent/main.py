from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from agents.generate_agent.spec.nodes.prepare_spec_input import prepare_spec_input
from agents.generate_agent.spec.nodes.page_briefs_node import page_briefs_node
from agents.generate_agent.spec.nodes.llm_design_requirements import llm_design_requirements
from agents.generate_agent.spec.nodes.unsplash_search_node import unsplash_search
from agents.generate_agent.nodes.init_project_node import _init_project_node
from agents.generate_agent.nodes.analyze_project_node import _analyze_project_node
from agents.generate_agent.nodes.reasoning_node import _reasoning_node
from agents.generate_agent.nodes.gather_context_node import _gather_context_node
from agents.generate_agent.nodes.prepare_context_node import _prepare_context_node
from agents.generate_agent.nodes.execute_node import _execute_node
from agents.generate_agent.nodes.check_step_file_node import _check_step_file_node
from agents.generate_agent.nodes.summarize_design_for_step_node import _summarize_design_for_step_node
from agents.generate_agent.nodes.verify_index_imports_node import (
    _verify_index_imports_node,
    _route_after_verify_index_imports,
)
from agents.generate_agent.nodes.fix_index_imports_llm_node import _fix_index_imports_llm_node
from agents.generate_agent.nodes.should_continue import (
    _should_continue_reasoning,
    _should_continue_after_check_step_file,
    _should_continue_gather,
    _should_continue_after_gather_tools,
    _should_continue_execute,
)
from agents.generate_agent.state import GenerateAgentState
from agents.generate_agent.llm.tools import get_gather_context_tools

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)


print("Building MULTI-MODEL agent graph...")
print("   Fork: init_project || prepare_spec_input → page_briefs → llm_design → unsplash → sync → analyze → …")


def _fork_pass(state: GenerateAgentState) -> dict:
    """Pass-through for fork: run init and spec pipeline in parallel."""
    return {}


def _sync_join(state: GenerateAgentState) -> dict:
    """Join: no state change, used only for routing to analyze when both branches are done."""
    return {}


# Build graph for multi-model agent
builder = StateGraph(GenerateAgentState)

# Fork: from start run init_project and spec pipeline in parallel
builder.add_node("fork", _fork_pass)
builder.add_node("prepare_spec_input", prepare_spec_input)
builder.add_node("page_briefs", page_briefs_node)
builder.add_node("llm_design_requirements", llm_design_requirements)
builder.add_node("unsplash_search", unsplash_search)
builder.add_node("init_project", _init_project_node)
builder.add_node("sync", _sync_join)

builder.set_entry_point("fork")
builder.add_edge("fork", "init_project")
builder.add_edge("fork", "prepare_spec_input")

# Spec pipeline: prepare_spec_input → page_briefs (Phase 1 per-page ТЗ) → llm_design_requirements → unsplash_search
builder.add_edge("prepare_spec_input", "page_briefs")
builder.add_edge("page_briefs", "llm_design_requirements")
builder.add_edge("llm_design_requirements", "unsplash_search")

# Both branches converge to sync; sync → analyze → reasoning (page scope is inside analyze)
builder.add_edge("init_project", "sync")
builder.add_edge("unsplash_search", "sync")
builder.add_node("analyze", _analyze_project_node)
builder.add_node("reasoning", _reasoning_node)
builder.add_node("check_step_file", _check_step_file_node)
builder.add_node("gather_context", _gather_context_node)
builder.add_node("gather_tools_execute", ToolNode(get_gather_context_tools(), handle_tool_errors=True))
builder.add_node("prepare_context", _prepare_context_node)
builder.add_node("summarize_design_for_step", _summarize_design_for_step_node)
builder.add_node("execute", _execute_node)

builder.add_conditional_edges(
    "sync",
    lambda s: "analyze" if (s.get("_init_done") and s.get("_spec_done")) else "sync",
    {"analyze": "analyze", "sync": "sync"},
)
builder.add_edge("analyze", "reasoning")

# Reasoning → check_step_file (or end if complete)
builder.add_node("verify_index_imports", _verify_index_imports_node)
builder.add_conditional_edges(
    "reasoning",
    _should_continue_reasoning,
    {
        "check_step_file": "check_step_file",
        "verify_index_imports": "verify_index_imports",
    },
)
builder.add_node("fix_index_imports_llm", _fix_index_imports_llm_node)
builder.add_conditional_edges(
    "verify_index_imports",
    _route_after_verify_index_imports,
    {"end": END, "fix_index_imports_llm": "fix_index_imports_llm"},
)
builder.add_edge("fix_index_imports_llm", "verify_index_imports")
# check_step_file → analyze (file already existed) | gather_context (missing file)
builder.add_conditional_edges(
    "check_step_file",
    _should_continue_after_check_step_file,
    {"analyze": "analyze", "gather_context": "gather_context"},
)

# Gather context → tools (if tool_calls) or prepare_context
builder.add_conditional_edges(
    "gather_context",
    _should_continue_gather,
    {"gather_tools_execute": "gather_tools_execute", "prepare_context": "prepare_context"},
)
# After gather_tools: if ready_to_execute → prepare_context, else → gather_context
builder.add_conditional_edges(
    "gather_tools_execute",
    _should_continue_after_gather_tools,
    {"prepare_context": "prepare_context", "gather_context": "gather_context"},
)
builder.add_edge("prepare_context", "summarize_design_for_step")
builder.add_edge("summarize_design_for_step", "execute")

# Execute (runs tools inline) → analyze | execute
builder.add_conditional_edges(
    "execute",
    _should_continue_execute,
    {"analyze": "analyze", "execute": "execute"},
)

graph = builder.compile()

print("Graph compiled successfully!")
print(
    "   Flow: ... → verify_index_imports ⇄ fix_index_imports_llm → END (при OK или лимите)"
)