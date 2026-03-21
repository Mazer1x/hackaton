# agents/validate_agent/llm/tools/fs_tools.py
"""
File system tools for the fix_deploy node, scoped to project_path.
All paths are resolved under project_path (relative or absolute under it).
shell_execute_in_project: allowlist only (npm run, npm install, npx astro, etc.).
"""
import os
import subprocess
from pathlib import Path
from typing import Optional

from langchain_core.tools import BaseTool, tool


# Allowed command prefixes for shell_execute_in_project (normalized: stripped, single spaces)
SHELL_ALLOWLIST_PREFIXES = (
    "npm run ",
    "npm install ",
    "npm install",
    "npm ci ",
    "npm ci",
    "npx astro ",
    "npx tailwindcss ",
    "npx create-astro ",
)


def _shell_command_allowed(command: str) -> bool:
    """True if command matches allowlist (npm run build, npm install, npx astro ..., etc.)."""
    normalized = " ".join(command.strip().split())
    if not normalized:
        return False
    normalized_lower = normalized.lower()
    return any(normalized_lower.startswith(p) for p in SHELL_ALLOWLIST_PREFIXES)


def _resolve_in_project(project_path: str, path: str) -> Optional[Path]:
    """Resolve path under project_path. Return None if outside project."""
    root = Path(project_path).resolve()
    if not root.exists():
        return None
    p = Path(path)
    if not p.is_absolute():
        p = (root / p).resolve()
    else:
        p = p.resolve()
    try:
        p.relative_to(root)
    except ValueError:
        return None
    return p


def get_fix_tools(project_path: str) -> list[BaseTool]:
    """
    Build read_file, write_file, list_directory, shell_execute scoped to project_path.
    Paths can be relative to project (e.g. 'astro.config.mjs', 'src/pages/index.astro')
    or absolute under project_path.
    """

    root = Path(project_path).resolve()

    @tool
    def read_file_in_project(path: str) -> str:
        """Read file contents. Path is relative to project (e.g. astro.config.mjs, src/pages/index.astro)."""
        try:
            p = _resolve_in_project(project_path, path)
            if p is None:
                return f"Access denied: path must be under project ({root}). Got: {path}"
            if not p.exists():
                return f"File not found: {path}"
            if not p.is_file():
                return f"This is a directory: {path}"
            return p.read_text(encoding="utf-8")
        except Exception as e:
            return f"Read error: {e!s}"

    @tool
    def write_file_in_project(path: str, content: str) -> str:
        """Create or overwrite file. Path is relative to project (e.g. astro.config.mjs)."""
        try:
            p = _resolve_in_project(project_path, path)
            if p is None:
                return f"Access denied: path must be under project ({root}). Got: {path}"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"File written: {path} ({len(content)} bytes)"
        except Exception as e:
            return f"Write error: {e!s}"

    @tool
    def list_directory_in_project(path: str = ".") -> str:
        """List directory contents. Path is relative to project (e.g. ., src, src/pages)."""
        try:
            p = _resolve_in_project(project_path, path)
            if p is None:
                return f"Access denied: path must be under project ({root}). Got: {path}"
            if not p.exists():
                return f"Directory not found: {path}"
            if not p.is_dir():
                return f"This is a file: {path}"
            items = [
                f"{'[DIR]' if x.is_dir() else '[FILE]'} {x.name}"
                for x in sorted(p.iterdir())
            ]
            return f"Contents of {path}:\n" + "\n".join(items) if items else f"Empty: {path}"
        except Exception as e:
            return f"Error: {e!s}"

    @tool
    def shell_execute_in_project(command: str) -> str:
        """Run a shell command in project path. Allowed: npm run build, npm install, npm ci, npx astro ..., npx tailwindcss ..., npx create-astro .... Other commands are rejected."""
        if not _shell_command_allowed(command):
            allowed = ", ".join(p.strip() for p in SHELL_ALLOWLIST_PREFIXES)
            return f"Command not allowed. Use only: {allowed} (e.g. npm run build, npm install, npx astro build)."
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=300,
                env={**os.environ, "CI": "1"},
            )
            out = []
            if result.stdout:
                out.append(f"STDOUT:\n{result.stdout.strip()}")
            if result.stderr:
                out.append(f"STDERR:\n{result.stderr.strip()}")
            text = "\n\n".join(out) if out else "(no output)"
            if result.returncode != 0:
                return f"Command failed (exit {result.returncode}):\n{text}"
            return f"Command OK:\n{text}"
        except subprocess.TimeoutExpired:
            return "Command timed out (300s)."
        except Exception as e:
            return f"Execution error: {e!s}"

    return [
        read_file_in_project,
        write_file_in_project,
        list_directory_in_project,
        shell_execute_in_project,
    ]
