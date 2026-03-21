"""
Check plan node: physical check (no AI) — which files from generation_plan exist on disk.
"""
from pathlib import Path

from agents.generate_agent.state import GenerateAgentState
from agents.generate_agent.nodes.agent_node import get_project_path


def _get_project_path_from_state(state: dict) -> str:
    path = state.get("project_path")
    if path:
        return str(Path(path).resolve())
    inp = state.get("input")
    if isinstance(inp, dict) and inp.get("project_path"):
        return str(Path(inp["project_path"]).resolve())
    return get_project_path()


def check_plan_node(state: GenerateAgentState) -> dict:
    """
    For each path in generation_plan, check if file exists under project_path.
    Returns plan_status: { "src/styles/custom.css": True, "src/layouts/BaseLayout.astro": False, ... }.
    """
    project_path = _get_project_path_from_state(state)
    plan = state.get("generation_plan") or []
    root = Path(project_path)
    plan_status = {}
    for rel in plan:
        full = (root / rel).resolve()
        try:
            plan_status[rel] = full.is_file()
        except Exception:
            plan_status[rel] = False
    done = sum(1 for v in plan_status.values() if v)
    print(f"CHECK_PLAN: {done}/{len(plan_status)} files exist")
    return {"plan_status": plan_status}
