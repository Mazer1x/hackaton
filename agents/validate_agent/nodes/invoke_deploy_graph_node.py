"""
Нода: вызывает граф deploy (deploy_git ↔ fix_deploy до выхода).
Возвращает обновления state: project_path, repo_name, deploy_log, deploy_url, fix_attempts, messages.
"""
from agents.validate_agent.deploy_graph import deploy_graph


async def invoke_deploy_graph_node(state: dict) -> dict:
    """Запуск подграфа деплоя; возвращает поля для слияния в state."""
    input_state = {
        "project_path": state.get("project_path"),
        "repo_name": state.get("repo_name"),
        "deploy_log": state.get("deploy_log"),
        "deploy_url": state.get("deploy_url"),
        "fix_attempts": state.get("fix_attempts"),
        "messages": state.get("messages") or [],
    }
    result = await deploy_graph.ainvoke(input_state)
    return {
        "project_path": result.get("project_path"),
        "repo_name": result.get("repo_name"),
        "deploy_log": result.get("deploy_log"),
        "deploy_url": result.get("deploy_url"),
        "fix_attempts": result.get("fix_attempts"),
        "messages": result.get("messages"),
    }
