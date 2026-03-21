"""
Граф: цикл deploy_git ↔ fix_deploy до успеха или одной попытки фикса.
Вход: project_path, repo_name (и опционально deploy_log, deploy_url, fix_attempts, messages).
Выход: project_path, repo_name, deploy_log, deploy_url, fix_attempts, messages.
"""
from pathlib import Path
from typing import Annotated, Optional

try:
    from typing_extensions import TypedDict
except ImportError:
    from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from agents.generate_agent.nodes.deploy_git_node import _deploy_git_node
from agents.generate_agent.state import _merge_project_path
from agents.validate_agent.nodes.fix_deploy_node import fix_deploy_node
from agents.validate_agent.nodes.should_fix_deploy import should_fix_after_deploy

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)


class DeployGraphState(TypedDict, total=False):
    """State для графа deploy: нужные поля для deploy_git и fix_deploy."""
    project_path: Annotated[Optional[str], _merge_project_path]
    repo_name: Optional[str]
    deploy_log: Optional[str]
    deploy_url: Optional[str]
    fix_attempts: Optional[int]
    messages: Annotated[list[BaseMessage], add_messages]


def _route_after_deploy(state: DeployGraphState) -> str:
    """Выход из подграфа: 'fix_deploy' (ещё раз) или 'end' (перейти к скриншотам)."""
    return should_fix_after_deploy(state)


builder = StateGraph(DeployGraphState)
builder.add_node("deploy_git", _deploy_git_node)
builder.add_node("fix_deploy", fix_deploy_node)
builder.set_entry_point("deploy_git")
builder.add_conditional_edges(
    "deploy_git",
    _route_after_deploy,
    {"fix_deploy": "fix_deploy", "run_screenshots": END},
)
builder.add_edge("fix_deploy", "deploy_git")

deploy_graph = builder.compile()
