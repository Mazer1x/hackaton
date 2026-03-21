# nodes/check_step_file_node.py
"""
Check Step File Node — runs after reasoning when action is create_file.
Checks if the target file already exists on disk. Used to skip execute and re-analyze when file was already created.
"""
from pathlib import Path

from agents.generate_agent.state import GenerateAgentState


def _check_step_file_node(state: GenerateAgentState) -> dict:
    """
    If reasoning_decision.action is create_file, check if file_path exists under project_path.
    Returns _step_file_existed (True → route to analyze; False → gather_context) and
    file_already_created_path (set when file exists, so reasoning can note "file already created").
    """
    decision = state.get("reasoning_decision") or {}
    action = decision.get("action", "")
    file_path = (decision.get("file_path") or "").strip().lstrip("/")
    project_path = (state.get("project_path") or "").strip()

    if action != "create_file" or not file_path or not project_path:
        return {
            "_step_file_existed": False,
            "file_already_created_path": None,
        }

    # Exceptions: never skip execute for global.css and index.astro (always allow create/overwrite)
    path_norm = file_path.lower().replace("\\", "/").rstrip("/")
    if path_norm.endswith("global.css") or path_norm.endswith("index.astro"):
        return {
            "_step_file_existed": False,
            "file_already_created_path": None,
        }

    full = Path(project_path) / file_path
    exists = full.is_file()

    if exists:
        print(f"CHECK_STEP_FILE: file already exists, skip execute → analyze → reasoning: {file_path}")

    return {
        "_step_file_existed": exists,
        "file_already_created_path": file_path if exists else None,
    }
