# nodes/analyze_project_node.py
"""
Analyze Project Node - scans project folder and provides structured information.
Runs BEFORE reasoning, so reasoning can see the full picture.
"""
import os
from pathlib import Path
from typing import Dict, List

from langchain_core.messages import AIMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES, RemoveMessage

from agents.generate_agent.state import GenerateAgentState
from agents.generate_agent.page_plan_context import page_scope_updates_for_analyze
from agents.generate_agent.utils import get_site_info
from agents.generate_agent.spec.utils.generation_plan import first_missing_plan_file


def _layout_section_to_component_filename(section: dict) -> str | None:
    """То же имя файла, что в mandate / summarize_design: hero → Hero.astro."""
    if not isinstance(section, dict):
        return None
    sid = (section.get("id") or section.get("role") or "").strip()
    if not sid:
        return None
    return sid.replace("_", " ").title().replace(" ", "") + ".astro"


def _missing_planned_components(src_path: Path, layout_spec: dict | None) -> list[str]:
    """Пути src/components/X.astro из layout_spec.sections, которых ещё нет на диске."""
    if not isinstance(layout_spec, dict):
        return []
    sections = layout_spec.get("sections") or []
    if not sections:
        return []
    comp_dir = src_path / "components"
    missing: list[str] = []
    for s in sections:
        fn = _layout_section_to_component_filename(s)
        if not fn:
            continue
        rel = f"src/components/{fn}"
        if not (comp_dir / fn).is_file():
            missing.append(rel)
    return missing


def scan_directory(path: Path, max_depth: int = 3, current_depth: int = 0) -> Dict:
    """
    Recursively scans directory and returns structure.
    """
    if current_depth >= max_depth or not path.exists():
        return {}
    
    result = {
        "files": [],
        "directories": [],
        "total_files": 0,
        "total_size": 0
    }
    
    try:
        for item in path.iterdir():
            # Ignore node_modules, .git, dist, .astro
            if item.name in ['node_modules', '.git', 'dist', '.astro', '__pycache__']:
                continue
            
            if item.is_file():
                try:
                    size = item.stat().st_size
                    result["files"].append({
                        "name": item.name,
                        "path": str(item.relative_to(path)),
                        "size": size,
                        "extension": item.suffix
                    })
                    result["total_files"] += 1
                    result["total_size"] += size
                except:
                    pass
            
            elif item.is_dir():
                subdir_info = scan_directory(item, max_depth, current_depth + 1)
                result["directories"].append({
                    "name": item.name,
                    "path": str(item.relative_to(path)),
                    "files_count": subdir_info.get("total_files", 0)
                })
                result["total_files"] += subdir_info.get("total_files", 0)
                result["total_size"] += subdir_info.get("total_size", 0)
    except PermissionError:
        pass
    
    return result


def analyze_project_structure(
    project_path: str,
    layout_spec: dict | None = None,
    generation_plan: list[str] | None = None,
) -> Dict:
    """
    Analyzes project structure and determines what has already been created.
    Если задан layout_spec с sections — complete только когда все запланированные .astro есть.
    """
    path = Path(project_path)
    
    if not path.exists():
        return {
            "exists": False,
            "empty": True,
            "status": "not_created",
            "message": "Project does not exist, need to create"
        }
    
    # CHECK FOR "JUNK" SUBFOLDERS (when npm create astro created a subfolder)
    # Look for subfolders with astro projects that agent accidentally created
    suspicious_subdirs = []
    try:
        for item in path.iterdir():
            if item.is_dir() and item.name not in ['node_modules', '.git', 'dist', '.astro', 'src', 'public', '.vscode']:
                # Check if there's an astro project there (or started installation)
                has_astro_files = (
                    (item / "package.json").exists() or 
                    (item / "astro.config.mjs").exists() or
                    (item / "package-lock.json").exists() or  # npm install started
                    (item / "node_modules").exists()  # dependencies installed
                )
                if has_astro_files:
                    suspicious_subdirs.append(item.name)
    except:
        pass
    
    if suspicious_subdirs:
        return {
            "exists": True,
            "status": "ERROR_SUBFOLDER",
            "message": f"ERROR: Agent created subfolders {suspicious_subdirs} instead of project in current directory!",
            "suspicious_subdirs": suspicious_subdirs,
            "fix_instructions": [
                f"1. Remove junk folders: rm -rf {' '.join(suspicious_subdirs)}",
                "2. Create project CORRECTLY: npm create astro@latest . -- --template minimal --install --yes --git --typescript strict",
                "3. MUST use DOT (.) in command to create in current directory!"
            ]
        }
    
    # Scan structure
    structure = scan_directory(path)
    
    # Determine key files
    key_files = {
        "package.json": (path / "package.json").exists(),
        "astro.config.mjs": (path / "astro.config.mjs").exists(),
        "tsconfig.json": (path / "tsconfig.json").exists(),
        "tailwind.config.mjs": (path / "tailwind.config.mjs").exists(),
    }
    
    # Check for important directories and files
    src_path = path / "src"
    has_src = src_path.exists()
    
    project_analysis = {
        "exists": True,
        "empty": structure["total_files"] == 0,
        "total_files": structure["total_files"],
        "total_size_kb": round(structure["total_size"] / 1024, 2),
        "key_files": key_files,
        "has_src": has_src,
    }
    
    # Analyze src/ structure
    if has_src:
        src_structure = {
            "styles": [],
            "layouts": [],
            "components": [],
            "pages": [],
            "scripts": []
        }
        
        # Styles
        styles_path = src_path / "styles"
        if styles_path.exists():
            src_structure["styles"] = [f.name for f in styles_path.glob("*.css")]
        
        # Layouts
        layouts_path = src_path / "layouts"
        if layouts_path.exists():
            src_structure["layouts"] = [f.name for f in layouts_path.glob("*.astro")]
        
        # Components
        components_path = src_path / "components"
        if components_path.exists():
            src_structure["components"] = [f.name for f in components_path.glob("*.astro")]
        
        # Pages
        pages_path = src_path / "pages"
        if pages_path.exists():
            src_structure["pages"] = [f.name for f in pages_path.glob("*.astro")]
        
        # Scripts
        scripts_path = src_path / "scripts"
        if scripts_path.exists():
            src_structure["scripts"] = (
                [f.name for f in scripts_path.glob("*.js")]
                + [f.name for f in scripts_path.glob("*.ts")]
            )
        
        project_analysis["src_structure"] = src_structure
    
    # Check if Tailwind is installed (astro add tailwind creates tailwind.config.mjs and adds @astrojs/tailwind)
    has_tailwind = key_files["tailwind.config.mjs"]
    if not has_tailwind and key_files["package.json"]:
        try:
            import json
            pkg_path = path / "package.json"
            if pkg_path.exists():
                pkg = json.loads(pkg_path.read_text())
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                has_tailwind = "@astrojs/tailwind" in deps or "tailwindcss" in deps
        except Exception:
            pass

    # Determine project status
    if not key_files["package.json"]:
        project_analysis["status"] = "empty"
        project_analysis["message"] = "Folder exists, but project not initialized"
    elif not key_files["astro.config.mjs"]:
        project_analysis["status"] = "created_incomplete"
        project_analysis["message"] = "Astro project created, need astro.config.mjs"
    elif not has_tailwind:
        project_analysis["status"] = "needs_tailwind"
        project_analysis["message"] = "Tailwind not installed. Run: npx astro add tailwind --yes"
    elif not has_src:
        project_analysis["status"] = "basic_setup"
        project_analysis["message"] = "Basic setup exists, need to create src/"
    else:
        # Check for important files
        has_custom_css = "custom.css" in project_analysis["src_structure"].get("styles", [])
        has_base_layout = any("Base" in f for f in project_analysis["src_structure"].get("layouts", []))
        components = project_analysis["src_structure"].get("components", [])
        has_components = len(components) >= 3  # Minimum 3 components!
        has_index = "index.astro" in project_analysis["src_structure"].get("pages", [])
        
        # Check that index.astro is not default
        index_is_real = False
        if has_index:
            index_path = src_path / "pages" / "index.astro"
            try:
                index_content = index_path.read_text()
                # Check that index imports BaseLayout and components
                index_is_real = (
                    "import" in index_content and 
                    "BaseLayout" in index_content and
                    len(components) > 0 and
                    any(comp.replace(".astro", "") in index_content for comp in components)
                )
            except:
                pass
        
        if not has_custom_css:
            project_analysis["status"] = "needs_styles"
            project_analysis["message"] = "Need custom.css with animations"
        elif not has_base_layout:
            project_analysis["status"] = "needs_layout"
            project_analysis["message"] = "Need BaseLayout.astro"
        else:
            planned_missing = _missing_planned_components(src_path, layout_spec)
            layout_sections = (
                (layout_spec or {}).get("sections") if isinstance(layout_spec, dict) else None
            )
            has_spec_plan = bool(layout_sections)

            if has_spec_plan and planned_missing:
                names = ", ".join(Path(p).name for p in planned_missing[:12])
                extra = f" (+{len(planned_missing) - 12} ещё)" if len(planned_missing) > 12 else ""
                project_analysis["status"] = "needs_planned_components"
                project_analysis["message"] = (
                    f"layout_spec: создай недостающие компоненты ({len(planned_missing)}): {names}{extra}"
                )
                project_analysis["layout_spec_missing_components"] = planned_missing
            elif (
                generation_plan
                and isinstance(generation_plan, list)
                and len(generation_plan) > 0
            ):
                missing_rel = first_missing_plan_file(str(path), generation_plan)
                if missing_rel:
                    project_analysis["status"] = "needs_plan_files"
                    project_analysis["message"] = (
                        f"По generation_plan не хватает файла: {missing_rel} (многостраничник — создай все страницы из плана)."
                    )
                    project_analysis["first_missing_plan_file"] = missing_rel
                elif not has_index or not index_is_real:
                    # План выполнен по файлам, но главная не собрана из компонентов
                    project_analysis["status"] = "needs_index"
                    project_analysis["message"] = (
                        "Нужен index.astro с BaseLayout и импортами компонентов (или доработай главную)."
                    )
                else:
                    project_analysis["status"] = "complete"
                    project_analysis["message"] = (
                        f"План выполнен: {len(generation_plan)} файлов по плану, главная OK"
                    )
            elif not has_spec_plan and len(components) < 3:
                project_analysis["status"] = "needs_components"
                project_analysis["message"] = f"Need minimum 3 components (current: {len(components)})"
            elif not has_index or not index_is_real:
                project_analysis["status"] = "needs_index"
                project_analysis["message"] = "Need index.astro that imports BaseLayout and components"
            else:
                project_analysis["status"] = "complete"
                project_analysis["message"] = (
                    f"Project ready: {len(components)} components, index.astro OK, layout_spec выполнен"
                    if has_spec_plan
                    else f"Project ready: {len(components)} components, index.astro imports everything"
                )
    
    return project_analysis


def _preserve_messages_until_first_ai(messages: list) -> list:
    """Keep only the user thread before the first AIMessage (drops reasoning/gather/execute history)."""
    out: list = []
    for m in messages:
        if isinstance(m, AIMessage):
            break
        out.append(m)
    return out


def _analyze_project_node(state: GenerateAgentState) -> dict:
    """
    Analyze Project Node: scans project and saves analysis to state.
    """
    from agents.generate_agent.nodes.agent_node import get_project_path
    
    # Get or set project_path
    project_path = state.get("project_path")
    if not project_path:
        project_path = get_project_path()
        Path(project_path).mkdir(parents=True, exist_ok=True)
    
    # Analyze project
    analysis = analyze_project_structure(
        project_path,
        layout_spec=state.get("layout_spec"),
        generation_plan=state.get("generation_plan"),
    )
    
    # Log results
    status = analysis.get("status", "unknown")
    message = analysis.get("message", "")
    
    print(f"PROJECT ANALYSIS:")
    print(f"   Status: {status}")
    print(f"   Message: {message}")
    print(f"   Total files: {analysis.get('total_files', 0)}")
    
    if analysis.get("has_src"):
        src = analysis.get("src_structure", {})
        print(f"   src/:")
        print(f"      - styles: {len(src.get('styles', []))} files")
        print(f"      - layouts: {len(src.get('layouts', []))} files")
        print(f"      - components: {len(src.get('components', []))} files")
        print(f"      - pages: {len(src.get('pages', []))} files")
    
    # Page scope (multi-site) merged here so the graph has one linear analyze step (no separate page_session node)
    scope = page_scope_updates_for_analyze(state)

    # Save analysis to state for reasoning; clear gather/execute scratch for next cycle
    out = {
        **scope,
        "project_analysis": analysis,
        "project_path": project_path,
        "loaded_skills_context": None,
        "step_design_summary": None,
    }
    # Reset message history to user thread only — prevents gather context from growing without bound
    preserved = _preserve_messages_until_first_ai(list(state.get("messages") or []))
    out["messages"] = [RemoveMessage(id=REMOVE_ALL_MESSAGES)] + preserved
    # Short site summary for reasoning/load_skills (saves tokens). Prefer ТЗ (project_spec), else json_data
    site_info = get_site_info(state)
    if site_info:
        out["site_info"] = site_info
    return out
