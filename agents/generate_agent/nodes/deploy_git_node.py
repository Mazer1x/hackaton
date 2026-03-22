"""
Git deploy node: initialize repo (if needed), commit and push to remote, then parse logs.

Expected state:
- project_path: путь к локальному проекту (Astro-сайт)
- repo_name: имя репозитория на git-сервере; если не задано — basename(project_path)

Remote template:
    git@45.90.35.151:sites/{repo_name}.git

Commands (idempotent по возможности):
- git init                         (если .git ещё нет)
- git add .
- git commit -m "initial"          (игнорируем "nothing to commit")
- git remote add origin <remote>   (если origin ещё не настроен)
- git branch -M main
- git push -u origin main

Результат:
- deploy_log: объединённый stdout/stderr всех git-команд
- deploy_url: строка после "DEPLOY_URL:" из вывода post-receive hook (если найдена)
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Tuple

from agents.generate_agent.nodes.agent_node import get_project_path
from agents.generate_agent.state import GenerateAgentState


def _get_project_path_from_state(state: dict) -> str:
    """project_path из state или из state['input']; fallback — get_project_path()."""
    path = state.get("project_path")
    if path:
        return path
    inp = state.get("input")
    if isinstance(inp, dict) and inp.get("project_path"):
        return inp["project_path"]
    return get_project_path()


def _run_git(
    args: list[str],
    cwd: str,
) -> Tuple[int, str, str]:
    """Run git command and return (code, stdout, stderr)."""
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError as e:
        # git не установлен или не найден в PATH
        msg = f"git not found: {e!s}"
        return 127, "", msg


def _ensure_git_repo(project_path: str) -> Tuple[bool, str]:
    """Ensure project_path is a git repo. Returns (ok, log_fragment)."""
    path = Path(project_path)
    log_parts: list[str] = []

    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)

    if (path / ".git").exists():
        return True, "git: repo already initialized\n"

    code, out, err = _run_git(["init"], cwd=project_path)
    log_parts.append(f"$ git init\n{out}{err}")
    return code == 0, "".join(log_parts)


def _repo_remote(repo_name: str) -> str:
    # Pattern: sites/{name}/1.git — post-receive expects login/number structure
    return f"git@45.90.35.151:sites/{repo_name}/1.git"


def _parse_deploy_url(output: str) -> str | None:
    """Extract DEPLOY_URL:... from combined stdout/stderr."""
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("DEPLOY_URL:"):
            return line.split("DEPLOY_URL:", 1)[1].strip()
    return None


# Строки, которые должны быть в .gitignore до git add . (чтобы не коммитить node_modules и т.д.)
_DEFAULT_GITIGNORE_LINES = [
    "node_modules/",
    ".env",
    ".env.*",
    "dist/",
    ".astro/",
    ".vercel/",
    ".turbo/",
]


def _ensure_gitignore(project_path: str) -> None:
    """Дополнить .gitignore в project_path нужными правилами, если их ещё нет."""
    path = Path(project_path)
    gitignore = path / ".gitignore"
    existing = set()
    if gitignore.exists():
        for line in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                existing.add(line)
    to_append = [line for line in _DEFAULT_GITIGNORE_LINES if line not in existing]
    if to_append:
        with open(gitignore, "a", encoding="utf-8") as f:
            if existing:
                f.write("\n")
            f.write("\n".join(to_append) + "\n")


def _deploy_git_node(state: GenerateAgentState) -> dict:
    """
    Run git init/add/commit/push and capture logs + DEPLOY_URL.
    Works with both GenerateAgentState and ValidateAgentState (project_path from state or input).
    """
    project_path = _get_project_path_from_state(state)
    path = Path(project_path)
    path.mkdir(parents=True, exist_ok=True)

    repo_name = state.get("repo_name") or (state.get("input") or {}).get("repo_name") or path.name
    remote_url = _repo_remote(repo_name)

    full_log_parts: list[str] = []

    # 1) git init (если нужно)
    ok, init_log = _ensure_git_repo(project_path)
    full_log_parts.append(init_log)
    if not ok:
        combined = "".join(full_log_parts)
        return {
            "project_path": project_path,
            "repo_name": repo_name,
            "deploy_log": combined,
            "deploy_url": _parse_deploy_url(combined),
        }

    # 2) убедиться, что .gitignore исключает node_modules и др. (до git add)
    _ensure_gitignore(project_path)

    # 2b) снять с отслеживания то, что теперь в .gitignore (если уже коммитили раньше)
    for entry in ("node_modules", "dist"):
        code_rm, out_rm, err_rm = _run_git(["rm", "-r", "--cached", entry], cwd=project_path)
        if code_rm == 0:
            full_log_parts.append(f"$ git rm -r --cached {entry}\n{out_rm}{err_rm}")

    # 3) git add .
    code, out, err = _run_git(["add", "."], cwd=project_path)
    full_log_parts.append(f"$ git add .\n{out}{err}")
    if code != 0:
        combined = "".join(full_log_parts)
        return {
            "project_path": project_path,
            "repo_name": repo_name,
            "deploy_log": combined,
            "deploy_url": _parse_deploy_url(combined),
        }

    # 4) git commit -m "initial" (допускаем отсутствие изменений)
    code, out, err = _run_git(["commit", "-m", "initial"], cwd=project_path)
    commit_log = f"$ git commit -m \"initial\"\n{out}{err}"
    full_log_parts.append(commit_log)
    if code != 0 and "nothing to commit" not in (out + err).lower():
        combined = "".join(full_log_parts)
        return {
            "project_path": project_path,
            "repo_name": repo_name,
            "deploy_log": combined,
            "deploy_url": _parse_deploy_url(combined),
        }

    # 5) git remote add origin <remote> (если origin ещё не задан)
    code, out, err = _run_git(["remote", "get-url", "origin"], cwd=project_path)
    if code != 0:
        code_add, out_add, err_add = _run_git(
            ["remote", "add", "origin", remote_url],
            cwd=project_path,
        )
        full_log_parts.append(f"$ git remote add origin {remote_url}\n{out_add}{err_add}")
        if code_add != 0:
            combined = "".join(full_log_parts)
            return {
                "project_path": project_path,
                "repo_name": repo_name,
                "deploy_log": combined,
                "deploy_url": _parse_deploy_url(combined),
            }
    else:
        full_log_parts.append(f"$ git remote get-url origin\n{out}{err}")

    # 6) git branch -M main
    code, out, err = _run_git(["branch", "-M", "main"], cwd=project_path)
    full_log_parts.append(f"$ git branch -M main\n{out}{err}")

    # 7) git push -u origin main
    code, out, err = _run_git(["push", "-u", "origin", "main"], cwd=project_path)
    push_log = f"$ git push -u origin main\n{out}{err}"
    full_log_parts.append(push_log)

    combined = "".join(full_log_parts)
    deploy_url = _parse_deploy_url(combined)

    return {
        "project_path": project_path,
        "repo_name": repo_name,
        "deploy_log": combined,
        "deploy_url": deploy_url,
    }

