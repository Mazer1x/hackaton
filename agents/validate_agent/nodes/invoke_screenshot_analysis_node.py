"""
Нода: вызывает граф screenshot_analysis (run → upload → analyze).
Граф определён в validate_agent.screenshot_analysis_graph.
"""
from agents.validate_agent.screenshot_analysis_graph import screenshot_analysis_graph


async def invoke_screenshot_analysis_node(state: dict) -> dict:
    """Вызов графа скриншотов; возвращает screenshot_* и validation_result."""
    input_state = {
        "project_path": state.get("project_path"),
        "site_url": state.get("site_url"),
        "repo_name": state.get("repo_name"),
        "deploy_url": state.get("deploy_url"),
        "screenshot_dir": state.get("screenshot_dir"),
        "site_info": state.get("site_info"),
        "site_target": state.get("site_target"),
        "json_data": state.get("json_data"),
        "project_spec": state.get("project_spec"),
        "generation_plan": state.get("generation_plan"),
    }
    result = await screenshot_analysis_graph.ainvoke(input_state)
    return {
        "screenshot_dir": result.get("screenshot_dir"),
        "screenshot_paths": result.get("screenshot_paths") or [],
        "screenshot_urls": result.get("screenshot_urls") or [],
        "screenshot_page_urls": result.get("screenshot_page_urls"),
        "screenshot_message": result.get("screenshot_message"),
        "validation_result": result.get("validation_result"),
    }
