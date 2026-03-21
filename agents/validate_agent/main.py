from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from agents.validate_agent.state import ValidateAgentState
from agents.validate_agent.nodes.invoke_deploy_graph_node import invoke_deploy_graph_node
from agents.validate_agent.nodes.invoke_screenshot_analysis_node import invoke_screenshot_analysis_node
from agents.validate_agent.nodes.fix_site_react_node import fix_site_react_node
from agents.validate_agent.nodes.should_fix_site import should_fix_site
from agents.validate_agent.nodes.git_commit_push_node import git_commit_push_node
from agents.validate_agent.nodes.delete_screenshots_node import delete_screenshots_node

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)


print("Building validate_agent graph...")

builder = StateGraph(ValidateAgentState)

builder.add_node("deploy", invoke_deploy_graph_node)
builder.add_node("analyze_screenshots", invoke_screenshot_analysis_node)
builder.add_node("fix_site_react", fix_site_react_node)
builder.add_node("git_commit_push", git_commit_push_node)
builder.add_node("delete_screenshots", delete_screenshots_node)

builder.set_entry_point("deploy")
builder.add_edge("deploy", "analyze_screenshots")
builder.add_conditional_edges(
    "analyze_screenshots",
    should_fix_site,
    {"fix_site_react": "fix_site_react", "end": END},
)
builder.add_edge("fix_site_react", "git_commit_push")
builder.add_edge("git_commit_push", "delete_screenshots")
builder.add_edge("delete_screenshots", "analyze_screenshots")

graph = builder.compile()

print("validate_agent graph compiled successfully!")
print("   Flow: deploy (subgraph) → analyze_screenshots → [if errors] fix_site_react → git_commit_push → delete_screenshots → analyze_screenshots (заново)... → END")
