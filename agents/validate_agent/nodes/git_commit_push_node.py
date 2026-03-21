# nodes/git_commit_push_node.py
"""
После fix_site_react: git add ., git commit -m "...", git push в project_path.
В validate_edit графе после этого — END; в validate_agent/main после этого могут идти другие ноды.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from agents.validate_agent.state import ValidateAgentState

COMMIT_MESSAGE = "fix: user-requested site edits"


def _run_git(cwd: str, *args: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = (proc.stdout or "").strip() + "\n" + (proc.stderr or "").strip()
        return proc.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return -1, "git command timed out (120s)"
    except FileNotFoundError:
        return 127, "git not found in PATH"


def git_commit_push_node(state: ValidateAgentState) -> dict:
    project_path = (state.get("project_path") or "").strip()
    if not project_path or not Path(project_path).exists():
        return {"deploy_log": (state.get("deploy_log") or "") + "\n[git_commit_push] skip: no project_path"}

    log_parts: list[str] = []

    code, out = _run_git(project_path, "add", ".")
    log_parts.append(f"$ git add .\n{out}")
    if code != 0:
        return {"deploy_log": (state.get("deploy_log") or "") + "\n" + "\n".join(log_parts)}

    code, out = _run_git(project_path, "commit", "-m", COMMIT_MESSAGE)
    log_parts.append(f"$ git commit -m \"{COMMIT_MESSAGE}\"\n{out}")
    # 1 = nothing to commit (working tree clean) — не ошибка
    if code != 0 and code != 1:
        return {"deploy_log": (state.get("deploy_log") or "") + "\n" + "\n".join(log_parts)}

    code, out = _run_git(project_path, "push")
    log_parts.append(f"$ git push\n{out}")
    if code != 0:
        return {"deploy_log": (state.get("deploy_log") or "") + "\n" + "\n".join(log_parts)}

    prev_log = state.get("deploy_log") or ""
    return {"deploy_log": prev_log + "\n[git_commit_push]\n" + "\n".join(log_parts)}
