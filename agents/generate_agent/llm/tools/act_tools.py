# llm/tools/act_tools.py
"""Basic tools for working with files and command line."""
import os
import subprocess
from pathlib import Path
from typing import Optional
from langchain_core.tools import tool, BaseTool


def _get_site_root() -> Path:
    """Site directory path (same as get_project_path in agent_node). Used to restrict read/list to site/."""
    # act_tools.py is in generate_agent/llm/tools/ → 5 levels up = repo root
    root = Path(__file__).resolve().parent.parent.parent.parent.parent
    return (root / "site").resolve()


def _resolve_within_site(path: str) -> Optional[Path]:
    """Resolve path to a real path under site/. Return None if outside site."""
    site_root = _get_site_root()
    p = Path(path)
    if not p.is_absolute():
        p = (site_root / p).resolve()
    else:
        p = p.resolve()
    try:
        p.relative_to(site_root)
    except ValueError:
        return None
    return p


@tool
def shell_execute(command: str, working_directory: Optional[str] = None) -> str:
    """
    Execute command in shell.
    
    Args:
        command: Command to execute
        working_directory: Working directory
        
    Returns:
        Command output
        
    Important for npm create astro:
    Correct format: npm create astro@latest . -- --template minimal --install --yes --git --typescript strict
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=180,  # 3 minutes for npm commands
            env={**os.environ, 'CI': '1'}  # CI=1 disables interactivity
        )
        
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        
        output_parts = []
        if stdout:
            output_parts.append(f"STDOUT:\n{stdout}")
        if stderr:
            output_parts.append(f"STDERR:\n{stderr}")
        
        output = "\n\n".join(output_parts) if output_parts else "(no output)"
        
        if result.returncode != 0:
            return f"Command failed with error (code {result.returncode}):\n{output}"
        
        return f"Command executed successfully:\n{output}"
        
    except subprocess.TimeoutExpired:
        return "Command exceeded timeout (180 seconds). Command may require interactive input."
    except Exception as e:
        return f"Execution error: {str(e)}"


@tool
def write_file(path: str, content: str) -> str:
    """
    Create or overwrite file.
    
    Args:
        path: Absolute path to file
        content: File content
        
    Returns:
        Success message
    """
    try:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        return f"File created: {path} ({len(content)} bytes)"
    except Exception as e:
        return f"Write error: {str(e)}"


@tool
def move_on(reason: str = "") -> str:
    """
    Signal that this execution step is done. Call this ONLY after you have already
    called write_file or write_file_in_site for the current task. Do not call move_on
    without performing the task first.
    """
    return "OK. Proceeding to next step."


@tool
def ready_to_execute(reason: str = "") -> str:
    """
    Signal that context gathering is done. Call this ONLY after you have loaded
    skills and read files (load_skill, read_file, etc.). Do not call ready_to_execute
    without gathering context first.
    """
    return "OK. Proceeding to prepare_context and execute."


@tool
def read_file(path: str) -> str:
    """
    Read file contents.
    
    Args:
        path: Absolute path to file
        
    Returns:
        File contents
    """
    try:
        file_path = Path(path)
        if not file_path.exists():
            return f"File not found: {path}"
        if not file_path.is_file():
            return f"This is a directory: {path}"
        return file_path.read_text(encoding='utf-8')
    except Exception as e:
        return f"Read error: {str(e)}"


@tool
def list_directory(path: str) -> str:
    """
    Show directory contents.
    
    Args:
        path: Absolute path to directory
        
    Returns:
        List of files and folders
    """
    try:
        dir_path = Path(path)
        if not dir_path.exists():
            return f"Directory not found: {path}"
        if not dir_path.is_dir():
            return f"This is a file: {path}"
        
        items = [f"{'[DIR]' if item.is_dir() else '[FILE]'} {item.name}" 
                 for item in sorted(dir_path.iterdir())]
        
        return f"Contents of {path}:\n" + "\n".join(items) if items else f"Empty: {path}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def read_file_in_site(path: str) -> str:
    """
    Read file contents. Allowed only inside the site/ directory (project path).
    Use relative paths (e.g. src/pages/index.astro) or paths under site/.
    
    Args:
        path: Path to file (relative to site/ or absolute under site/)
        
    Returns:
        File contents
    """
    try:
        file_path = _resolve_within_site(path)
        if file_path is None:
            site_root = _get_site_root()
            return f"Access denied: path must be under site directory ({site_root}). Got: {path}"
        if not file_path.exists():
            return f"File not found: {path}"
        if not file_path.is_file():
            return f"This is a directory: {path}"
        return file_path.read_text(encoding='utf-8')
    except Exception as e:
        return f"Read error: {str(e)}"


@tool
def list_directory_in_site(path: str) -> str:
    """
    Show directory contents. Allowed only inside the site/ directory (project path).
    Use relative paths (e.g. src, src/components) or paths under site/.
    
    Args:
        path: Path to directory (relative to site/ or absolute under site/)
        
    Returns:
        List of files and folders
    """
    try:
        dir_path = _resolve_within_site(path)
        if dir_path is None:
            site_root = _get_site_root()
            return f"Access denied: path must be under site directory ({site_root}). Got: {path}"
        if not dir_path.exists():
            return f"Directory not found: {path}"
        if not dir_path.is_dir():
            return f"This is a file: {path}"
        items = [f"{'[DIR]' if item.is_dir() else '[FILE]'} {item.name}"
                 for item in sorted(dir_path.iterdir())]
        return f"Contents of {path}:\n" + "\n".join(items) if items else f"Empty: {path}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def write_file_in_site(path: str, content: str) -> str:
    """
    Create or overwrite file. Allowed only inside the site/ directory (project path).
    Use relative paths (e.g. src/pages/index.astro, src/styles/custom.css).
    
    Args:
        path: Path to file (relative to site/ or absolute under site/)
        content: File content
        
    Returns:
        Success message
    """
    try:
        file_path = _resolve_within_site(path)
        if file_path is None:
            site_root = _get_site_root()
            return f"Access denied: path must be under site directory ({site_root}). Got: {path}"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"File created: {path} ({len(content)} bytes)"
    except Exception as e:
        return f"Write error: {str(e)}"


# ============================================================================
# SKILLS TOOLS - Progressive Disclosure Pattern
# ============================================================================
# Loadable: top-level llm/skills/*.md and llm/skills/frontend/*.md (no planning/).
# ТЗ-only (design-brief, design-generation) live in llm/skills/planning/ — not visible here.


def _get_loadable_skills_dir() -> Path:
    """Base skills directory (load_skill/list_skills scan this + frontend/ subdir)."""
    return Path(__file__).resolve().parent.parent / "skills"


def _find_loadable_skill_path(skill_name: str) -> Optional[Path]:
    """Resolve skill file: top-level skills/ or skills/frontend/ only. Returns None if not found."""
    base = _get_loadable_skills_dir()
    for subdir in ("", "frontend"):
        path = (base / subdir / f"{skill_name}.md").resolve() if subdir else (base / f"{skill_name}.md").resolve()
        if path.is_file():
            return path
    return None


def _iter_loadable_skill_files():
    """Yield all .md skill files from loadable locations (top-level + frontend/)."""
    base = _get_loadable_skills_dir()
    for subdir in ("", "frontend"):
        dir_path = base / subdir if subdir else base
        if dir_path.is_dir():
            for f in sorted(dir_path.glob("*.md")):
                if f.is_file():
                    yield f


@tool
def load_skill(skill_name: str) -> str:
    """Load a specialized skill for domain expertise.
    
    Skills provide detailed instructions, guidelines, and best practices for specific tasks.
    Use this tool when you need specialized knowledge or detailed instructions.
    
    Available skills (from loadable dirs: top-level + frontend/):
    - frontend-design: Create distinctive, production-grade UI with bold aesthetics
    - frontend-astro: Astro + Tailwind v4 implementation (structure, custom.css, layout order)
    
    Args:
        skill_name: Name of the skill to load (e.g., 'frontend-design')
        
    Returns:
        Full skill content with instructions, guidelines, and examples.
        
    Example:
        When creating a Hero component, load the frontend-design skill:
        load_skill("frontend-design")
    """
    try:
        skill_path = _find_loadable_skill_path(skill_name)
        if skill_path is None:
            available_skills = sorted({f.stem for f in _iter_loadable_skill_files()})
            return f"Skill '{skill_name}' not found.\nAvailable skills: {', '.join(available_skills) if available_skills else 'none'}"
        print(f"Loading skill: {skill_name}")
        content = skill_path.read_text(encoding='utf-8')
        print(f"Skill loaded: {skill_name} ({len(content)} chars)")
        return content
    except Exception as e:
        return f"Error loading skill: {str(e)}"


@tool
def list_skills() -> str:
    """List all available skills with descriptions.
    
    Returns skills from loadable locations (top-level skills/ and skills/frontend/).
    Use this tool to discover what skills are available before loading one.
    """
    try:
        skills = []
        for skill_file in _iter_loadable_skill_files():
            skill_name = skill_file.stem
            try:
                content = skill_file.read_text(encoding='utf-8')
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        frontmatter = parts[1]
                        for line in frontmatter.split('\n'):
                            if line.startswith('description:'):
                                desc = line.replace('description:', '').strip()
                                skills.append(f"- **{skill_name}**: {desc[:100]}...")
                                break
                        else:
                            skills.append(f"- **{skill_name}**: Available")
                    else:
                        skills.append(f"- **{skill_name}**: Available")
                else:
                    skills.append(f"- **{skill_name}**: Available")
            except Exception:
                skills.append(f"- **{skill_name}**: Available")
        if not skills:
            return "No skills found in the skills directory."
        result = "Available Skills:\n\n" + "\n".join(skills)
        result += "\n\nUse load_skill(skill_name) to load a skill and get detailed instructions."
        return result
    except Exception as e:
        return f"Error listing skills: {str(e)}"
