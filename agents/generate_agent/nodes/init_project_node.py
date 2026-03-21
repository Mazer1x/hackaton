# nodes/init_project_node.py
"""
Init project node: run 2 commands in sequence before analyze (linear, no LLM).
Creates Astro project and adds Tailwind when the project is empty or missing Tailwind.
Uses create-astro@4 (Node 20+). Non-interactive: CI=1, npx --yes.

Writes astro.config.mjs with `base` from repo_name (or project folder name) so deploy URLs
like https://automatoria.ru/{repo_name}/... match internal links (see site/src/utils/withBase.ts).
"""
import os
import re
import subprocess
from pathlib import Path

from agents.generate_agent.state import GenerateAgentState
from agents.generate_agent.nodes.agent_node import get_project_path

# Non-interactive env so npm/npx never prompt "Ok to proceed? (y)"
_INIT_ENV = {**os.environ, "CI": "1", "npm_config_yes": "true"}

# npx --yes avoids "Need to install ... Ok to proceed?". create-astro@4 supports Node 20; @5 requires Node 22+
INIT_COMMANDS = [
    "npx --yes create-astro@4 . -- --template minimal --install --yes --git --typescript strict",
    "npx --yes astro add tailwind --yes",
]

# Retries for tailwind add (often fails with network timeout)
TAILWIND_ADD_RETRIES = 2


def _run_init_commands(project_path: str) -> None:
    """Run INIT_COMMANDS in sequence. Skips create if package.json exists; skips tailwind if already present."""
    path = Path(project_path)
    path.mkdir(parents=True, exist_ok=True)

    has_package = (path / "package.json").exists()
    has_tailwind = (path / "tailwind.config.mjs").exists()

    for i, cmd in enumerate(INIT_COMMANDS):
        if i == 0 and has_package:
            print("Init: package.json exists, skipping npm create astro")
            continue
        if i == 1 and has_tailwind:
            print("Init: Tailwind already present, skipping astro add tailwind")
            continue
        print(f"Init: running [{i + 1}/2] {cmd[:60]}...")
        try:
            subprocess.run(
                cmd,
                shell=True,
                cwd=project_path,
                check=True,
                timeout=300,
                capture_output=False,
                env=_INIT_ENV,
            )
        except subprocess.CalledProcessError as e:
            if i == 0:
                print(
                    "Init: create-astro failed. If you see 'Node.js v20... unsupported' or 'use Node.js v22', "
                    "upgrade: nvm install 22 && nvm use 22 (or install Node 22 from nodejs.org)."
                )
            if i == 1:
                tailwind_ok = False
                for attempt in range(TAILWIND_ADD_RETRIES):
                    print(f"Init: astro add tailwind failed (attempt {attempt + 2}/{TAILWIND_ADD_RETRIES + 1}), retrying...")
                    try:
                        subprocess.run(
                            cmd,
                            shell=True,
                            cwd=project_path,
                            check=True,
                            timeout=300,
                            capture_output=False,
                            env=_INIT_ENV,
                        )
                        tailwind_ok = True
                        break
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                        pass
                if not tailwind_ok:
                    print(
                        "Init: astro add tailwind failed after retries (e.g. network timeout). "
                        "Run 'npx astro add tailwind --yes' in project dir later. Continuing."
                    )
                    return
            else:
                print(f"Init: command failed with code {e.returncode}")
                raise
        except subprocess.TimeoutExpired:
            if i == 1:
                print(
                    "Init: astro add tailwind timed out. "
                    "Run 'npx astro add tailwind --yes' in project dir later. Continuing."
                )
                return
            print("Init: command timed out")
            raise


def _resolve_project_path(state: GenerateAgentState) -> str:
    """project_path из state, из state['input'] (LangGraph Studio) или get_project_path()."""
    project_path = (state.get("project_path") or "").strip()
    if not project_path and isinstance(state.get("input"), dict):
        project_path = (state.get("input", {}).get("project_path") or "").strip()
    if not project_path:
        project_path = get_project_path()
    return str(Path(project_path).resolve())


def _resolve_repo_name(state: GenerateAgentState, project_path: str) -> str:
    """Имя репозитория на automatoria (sites/{repo}.git) — как в deploy_git_node."""
    name = (state.get("repo_name") or "").strip()
    if not name and isinstance(state.get("input"), dict):
        name = (state.get("input") or {}).get("repo_name") or ""
        name = str(name).strip()
    if not name:
        name = Path(project_path).name
    return name


def _sanitize_base_segment(name: str) -> str:
    """Сегмент пути для Astro base: только безопасные символы."""
    s = name.strip().strip("/")
    if not s:
        return ""
    if re.match(r"^[a-zA-Z0-9._-]+$", s):
        return s
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", s).strip("-") or ""


def _write_astro_config_with_base(project_path: str, repo_name: str) -> None:
    """
    Пишет site/astro.config.mjs с base: '/{repo}' + trailingSlash, чтобы ссылки шли на
    https://automatoria.ru/{repo}/ и https://automatoria.ru/{repo}/history/ (без отдельного порта).
    """
    seg = _sanitize_base_segment(repo_name)
    # Локальная разработка без сегмента — base '/'
    base_js = '"/"' if not seg else repr(f"/{seg}")

    content = f"""// @ts-check
// Auto-updated by init_project_node (repo_name → base). Safe to edit.
import {{ defineConfig }} from 'astro/config';

import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
// trailingSlash: static hosts (nginx) map /repo/history/ → history/index.html; /repo/history often 404.
export default defineConfig({{
  base: {base_js},
  trailingSlash: "always",
  vite: {{
    plugins: [tailwindcss()]
  }}
}});
"""
    cfg = Path(project_path) / "astro.config.mjs"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(content, encoding="utf-8")
    print(f"Init: wrote {cfg} with base={base_js}")


# Canonical helper for deploy subpaths; synced with repo site/src/utils/withBase.ts
_WITH_BASE_TS = r"""/**
 * Ссылки под Astro `base` и `trailingSlash: 'always'`.
 * Используйте import.meta.env.BASE_URL — не хардкодьте slug репозитория.
 */
export function withBase(path: string): string {
  const base = import.meta.env.BASE_URL || "/";
  const root = base.endsWith("/") ? base : `${base}/`;
  const clean = path.replace(/^\/+/, "").replace(/\/+$/, "");
  if (!clean) {
    return root;
  }
  return `${root}${clean}/`;
}
"""


def _write_with_base_util(project_path: str) -> None:
    """Всегда пишет src/utils/withBase.ts — нужен execute для любых страниц под /{repo}/."""
    util = Path(project_path) / "src" / "utils" / "withBase.ts"
    util.parent.mkdir(parents=True, exist_ok=True)
    util.write_text(_WITH_BASE_TS, encoding="utf-8")
    print(f"Init: wrote {util}")


def _init_project_node(state: GenerateAgentState) -> dict:
    """
    Linear init: run 2 commands (create astro, add tailwind) then pass through to analyze.
    No branching, no tools — just subprocess calls.
    """
    project_path = _resolve_project_path(state)
    Path(project_path).mkdir(parents=True, exist_ok=True)

    has_package = (Path(project_path) / "package.json").exists()
    has_tailwind = (Path(project_path) / "tailwind.config.mjs").exists()
    print(f"Init: project_path={project_path!r}, has_package={has_package}, has_tailwind={has_tailwind}")

    _run_init_commands(project_path)

    repo = _resolve_repo_name(state, project_path)
    _write_astro_config_with_base(project_path, repo)
    _write_with_base_util(project_path)

    return {
        "project_path": project_path,  # resolved absolute path
        "repo_name": repo,
        "_init_done": True,
    }
