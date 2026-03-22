# nodes/reasoning_node.py
"""
Reasoning Node - uses Claude 3.5 Sonnet for OBSERVE + THINK.
Analyzes situation and decides what to do next, but does NOT generate code.
"""
import json
import os
import uuid
from pathlib import Path
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

try:
    from openai import PermissionDeniedError as OpenAIPermissionDeniedError
except ImportError:
    OpenAIPermissionDeniedError = Exception  # noqa: A001

from agents.generate_agent.state import GenerateAgentState
from agents.generate_agent.utils import (
    get_user_request,
    get_site_info,
    get_content_brief,
    get_spec_sections,
    get_spec_blocks,
    get_design_spec,
    get_design_brief,
    get_site_target_layout_mandate,
    get_spec_pipeline_mandate,
)
from agents.generate_agent.llm.chat_factory import get_chat_llm
from agents.generate_agent.llm.tools.reasoning_decision_tools import get_reasoning_decision_tools


REASONING_PROMPT = """You are the REASONING module of an autonomous Frontend Builder Agent.

Your task: OBSERVE + THINK, then DECIDE by calling exactly one tool.

You analyze the current situation and decide WHAT needs to be done next.
Actual actions (code generation) will be performed by another model.
Project init (Astro + Tailwind) is already done — you only decide: create_file_step or complete_step.

===================================================================
YOUR ROLE
===================================================================

1. OBSERVE - Use PROJECT ANALYSIS (status and src/ structure — which files exist).
2. THINK - status is "complete"? → call complete_step(reasoning="..."). Else → call create_file_step(file_path, file_type, purpose, reasoning, key_requirements, optional recommended_skill).
3. DECIDE - Call exactly one tool: create_file_step OR complete_step. No other output.

Order for create_file: custom.css → BaseLayout.astro → components (Hero, About, etc.) → page(s): index.astro for home, plus other src/pages/*.astro for multi-page sites (see generation_plan / canonical.pages).
CRITICAL: Call complete_step ONLY when project_analysis.status is "complete". If status is "needs_planned_components", create_file_step for the NEXT missing component from layout_spec (see message / layout_spec_missing_components order). If status is "needs_plan_files", create the file in project_analysis.first_missing_plan_file. Otherwise call create_file_step for the next missing piece.
If CONTENT BRIEF / SITE SECTIONS are provided: component names and order MUST follow them.
For create_file_step, add key_requirements that push DISTINCTIVE design (unique font, animations, bold palette).
Section components: asymmetric layout, key_requirements like "60-40 grid", "one focal + supporting", "varied section heights"."""


def _make_blocked_decision(err_msg: str) -> dict:
    """Build reasoning_decision when API blocks the request (e.g. content policy)."""
    return {
        "action": "error",
        "reasoning": (
            f"API blocked the request ({err_msg}). "
            "Use REASONING_MODEL (OpenRouter) or simplify the input."
        ),
        "done": False,
    }


def _get_reasoning_llm():
    """Create LLM for reasoning (OpenRouter)."""
    model = os.getenv("REASONING_MODEL") or os.getenv("OPENROUTER_MODEL")
    return get_chat_llm(
        model=model,
        temperature=0.5,
        parallel_tool_calls=False,
        reasoning_enabled=False,
    )


def _decision_from_tool_call(tc: dict) -> dict:
    """Build reasoning_decision from a single tool call (name + args)."""
    name = (tc.get("name") or "").strip()
    args = tc.get("args") or {}
    if name == "complete_step":
        return {
            "action": "complete",
            "reasoning": args.get("reasoning", "Project complete."),
            "done": True,
        }
    if name == "create_file_step":
        file_path = (args.get("file_path") or "").strip().lstrip("/")
        if not file_path.startswith("src/"):
            file_path = "src/" + file_path.lstrip("/") if file_path else "src/styles/custom.css"
        key_reqs = args.get("key_requirements")
        if not isinstance(key_reqs, list):
            key_reqs = [key_reqs] if key_reqs else []
        decision = {
            "action": "create_file",
            "file_path": file_path,
            "file_type": args.get("file_type", "astro_component"),
            "purpose": args.get("purpose", ""),
            "key_requirements": key_reqs,
            "reasoning": args.get("reasoning", ""),
            "done": False,
        }
        if args.get("recommended_skill"):
            decision["recommended_skill"] = args["recommended_skill"]
        return decision
    return {"action": "error", "reasoning": f"Unknown tool: {name}", "done": False}


def _reasoning_node(state: GenerateAgentState) -> dict:
    """
    Reasoning Node: analyzes situation and decides what to do next.
    Uses Claude 3.5 Sonnet (cheaper).
    """
    iteration = state.get("iteration_count", 0)
    project_analysis = state.get("project_analysis", {})
    
    # Get or set project_path
    from agents.generate_agent.nodes.agent_node import get_project_path
    project_path = state.get("project_path")
    if not project_path:
        project_path = get_project_path()
        # Create directory if it doesn't exist
        Path(project_path).mkdir(parents=True, exist_ok=True)
    
    # Get original user request (supports both message objects and dicts from API)
    user_request = get_user_request(state.get("messages", []))
    
    # Short site theme for reasoning (saves tokens); full content_brief below for section/block hints. Prefer ТЗ (project_spec).
    site_info = get_site_info(state)
    content_brief = get_content_brief(state)
    arch_sections = get_spec_sections(state)
    arch_blocks = get_spec_blocks(state)
    
    content_and_arch = ""
    if content_brief or arch_sections or arch_blocks:
        content_and_arch = """
CONTENT BRIEF (from JSON) — USE THIS CONTENT IN THE SITE, not generic placeholders!
"""
        if content_brief:
            content_and_arch += content_brief + "\n\n"
        if arch_sections:
            content_and_arch += f"SITE SECTIONS (order): {', '.join(arch_sections)}\n\n"
        if arch_blocks:
            content_and_arch += "BLOCKS (content hints per section):\n"
            for b in arch_blocks[:15]:
                btype = b.get("type", "")
                content = b.get("content", {})
                content_and_arch += f"  - {btype}: {content}\n"
        content_and_arch += """
When creating components: Hero = first section content, About = brand/description, Services = offer, etc.
All headings, CTAs, and text MUST come from the content brief above!
"""
    design_spec = get_design_spec(state)
    design_brief_full = get_design_brief(state)
    design_block = ""
    if design_brief_full:
        design_block = "\n=== FULL DESIGN BRIEF (from planning — section concepts, UI Kit, animations) ===\n" + design_brief_full[:8000] + "\n=== END DESIGN BRIEF ===\n"
    elif design_spec:
        design_block = "\nDESIGN (from planning — follow for custom.css and components):\n"
        if design_spec.get("palette"):
            design_block += f"  Palette: {design_spec.get('palette')}\n"
        if design_spec.get("typography"):
            design_block += f"  Typography: {design_spec.get('typography')}\n"
        if design_spec.get("mood"):
            design_block += f"  Mood: {design_spec.get('mood')}\n"
        if design_spec.get("key_requirements"):
            reqs = design_spec.get("key_requirements", [])
            design_block += "  Key requirements: " + "; ".join(str(r) for r in reqs) + "\n"
    
    # Form detailed project information
    project_info = ""
    if project_analysis:
        status = project_analysis.get("status", "unknown")
        message = project_analysis.get("message", "")
        
        project_info = f"""
PROJECT ANALYSIS:
   Status: {status}
   Message: {message}
   Total files: {project_analysis.get('total_files', 0)}
"""
        
        if project_analysis.get("has_src"):
            src = project_analysis.get("src_structure", {})
            project_info += f"""
   src/ structure:
      - styles/: {', '.join(src.get('styles', [])) or '(empty)'}
      - layouts/: {', '.join(src.get('layouts', [])) or '(empty)'}
      - components/: {', '.join(src.get('components', [])) or '(empty)'}
      - pages/: {', '.join(src.get('pages', [])) or '(empty)'}
"""
    
    site_target_block = get_site_target_layout_mandate(state)
    spec_mandate = get_spec_pipeline_mandate(state)
    spec_combined = ""
    if site_target_block:
        spec_combined += site_target_block
    if spec_mandate:
        spec_combined += spec_mandate
    spec_note = "\nSPEC PIPELINE is active: section order and design below MUST be followed.\n" if spec_mandate else ""
    site_block = f"\nSITE (theme, use for decisions): {site_info}\n" if site_info else ""
    status = project_analysis.get("status", "unknown")
    gp = state.get("generation_plan") or []
    plan_block = ""
    if isinstance(gp, list) and gp:
        lines = "\n".join(f"  - {p}" for p in gp[:50])
        extra = f"\n  ... ({len(gp)} paths total)" if len(gp) > 50 else ""
        plan_block = f"\nGENERATION_PLAN (create missing files in this order — multi-page includes several src/pages/*.astro):\n{lines}{extra}\n"
    file_already_note = ""
    file_already_created_path = state.get("file_already_created_path")
    if file_already_created_path:
        file_already_note = f"""
*** NOTE: The file {file_already_created_path} was already present (skipped). Do NOT create it again — choose the NEXT missing file or call complete_step if the project is done. ***
"""
    context = f"""
{spec_combined}{spec_note}{plan_block}
ITERATION {iteration + 1}
{site_block}
USER REQUEST:
{user_request}
{content_and_arch}
{design_block}

PROJECT_PATH: {project_path}
{project_info}
{file_already_note}

===================================================================
YOUR TASK
===================================================================

OBSERVE: Use PROJECT ANALYSIS status and src structure above (what files exist).
THINK: status is "{status}". If status is "complete" → output "complete". Else → create_file for the next missing piece. If GENERATION_PLAN is listed above, follow it (styles → layout → components → every page file including index.astro and other routes).
DECIDE: Output JSON decision.

If status is not "complete", you MUST call create_file_step (never complete_step). Only when status is "complete" may you call complete_step.

What's next? Call exactly one tool: create_file_step or complete_step.
"""
    prompt_messages = [
        SystemMessage(content=REASONING_PROMPT),
        HumanMessage(content=context),
    ]
    llm = _get_reasoning_llm()
    tools = get_reasoning_decision_tools()
    llm_with_tools = llm.bind_tools(tools, tool_choice="any")
    try:
        response = llm_with_tools.invoke(prompt_messages)
    except OpenAIPermissionDeniedError as e:
        err_msg = str(e).strip() or "Your request was blocked."
        print(f"REASONING API BLOCKED: {err_msg}")
        decision = _make_blocked_decision(err_msg)
        return {
            "messages": [],
            "reasoning_decision": decision,
            "iteration_count": iteration + 1,
            "project_path": project_path,
        }
    except Exception as e:
        # Upstream can return "blocked" as other exception types (e.g. APIError with message "blocked")
        err_msg = str(e).strip() or ""
        if "blocked" in err_msg.lower() or "request was blocked" in err_msg.lower():
            print(f"REASONING API BLOCKED: {err_msg}")
            decision = _make_blocked_decision(err_msg)
            return {
                "messages": [],
                "reasoning_decision": decision,
                "iteration_count": iteration + 1,
                "project_path": project_path,
            }
        raise

    # Parse decision: from tool call (preferred) or fallback to JSON in content
    decision = None
    tool_calls = getattr(response, "tool_calls", None) or []
    if tool_calls:
        tc = tool_calls[0]
        if isinstance(tc, dict):
            name = tc.get("name") or (tc.get("function") or {}).get("name") or ""
            args = tc.get("args")
            if args is None and tc.get("function"):
                raw = (tc["function"] or {}).get("arguments") or "{}"
                args = json.loads(raw) if isinstance(raw, str) else raw
            decision = _decision_from_tool_call({"name": name, "args": args or {}})
        else:
            name = getattr(tc, "name", "") or (getattr(tc, "function", None) or {}).get("name", "")
            args = getattr(tc, "args", None)
            if args is None and hasattr(tc, "function"):
                f = getattr(tc, "function", None) or {}
                raw = f.get("arguments", "{}") if isinstance(f, dict) else getattr(f, "arguments", "{}")
                args = json.loads(raw) if isinstance(raw, str) else raw
            decision = _decision_from_tool_call({"name": name, "args": args or {}})
    if decision is None:
        try:
            content = (response.content or "").strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            decision = json.loads(content)
        except Exception as e:
            print(f"Failed to parse decision (no tool call, JSON fallback failed): {e}")
            decision = {"action": "error", "reasoning": str(e), "done": False}

    action = decision.get("action", "")
    generation_plan = state.get("generation_plan") or []
    plan_status = state.get("plan_status") or {}
    status = project_analysis.get("status", "unknown")

    # Corrections: never "complete" when plan or status say otherwise
    if action == "complete" and plan_status and not all(plan_status.values()):
        for path in generation_plan:
            if not plan_status.get(path, True):
                print(f"CORRECTION: plan has missing file but model said complete → forcing create_file {path}")
                decision = {
                    "action": "create_file",
                    "file_path": path,
                    "file_type": "css" if path.endswith(".css") else "layout" if "layouts" in path else "astro_component" if "components" in path else "page",
                    "purpose": f"Next in plan: create {Path(path).name}",
                    "reasoning": f"Plan status: {path} is missing. Create it.",
                    "done": False,
                }
                action = "create_file"
                break
    elif action == "complete" and status == "needs_planned_components":
        missing = project_analysis.get("layout_spec_missing_components") or []
        path_part = missing[0] if missing else "src/components/Hero.astro"
        name = Path(path_part).name
        print(f"CORRECTION: layout_spec incomplete → create_file {path_part}")
        decision = {
            "action": "create_file",
            "file_path": path_part,
            "file_type": "astro_component",
            "purpose": f"Компонент из layout_spec: {name}",
            "reasoning": f"Статус needs_planned_components. Следующий файл по спеке: {name}.",
            "done": False,
        }
        action = "create_file"
    elif action == "complete" and status == "needs_plan_files":
        path_part = (project_analysis.get("first_missing_plan_file") or "src/styles/custom.css").strip()
        name = Path(path_part).name
        ft = (
            "css" if path_part.endswith(".css") else "layout"
            if "layouts" in path_part
            else "astro_component"
            if "components" in path_part
            else "page"
        )
        print(f"CORRECTION: needs_plan_files → create_file {path_part}")
        decision = {
            "action": "create_file",
            "file_path": path_part,
            "file_type": ft,
            "purpose": f"Следующий файл по generation_plan: {name}",
            "reasoning": f"Статус needs_plan_files — создай {path_part} (многостраничник: все страницы из плана).",
            "done": False,
        }
        action = "create_file"
    elif action == "complete" and status != "complete":
        next_file = {
            "needs_tailwind": ("src/styles/custom.css", "custom.css", "Tailwind will be fixed by init; create custom.css first"),
            "needs_styles": ("src/styles/custom.css", "custom.css", "Need custom.css with animations"),
            "needs_layout": ("src/layouts/BaseLayout.astro", "BaseLayout.astro", "Need BaseLayout.astro"),
            "needs_components": ("src/components/Hero.astro", "Hero.astro", "Need more components"),
            "needs_index": ("src/pages/index.astro", "index.astro", "Need index.astro importing BaseLayout and components"),
            "needs_planned_components": ("src/components/Hero.astro", "Hero.astro", "layout_spec: досоздай компоненты"),
            "needs_plan_files": ("src/pages/index.astro", "index.astro", "По плану не хватает файла — см. first_missing_plan_file"),
            "basic_setup": ("src/styles/custom.css", "custom.css", "Create custom.css first"),
            "empty": ("src/styles/custom.css", "custom.css", "Project empty; create custom.css"),
            "not_created": ("src/styles/custom.css", "custom.css", "Create custom.css"),
        }.get(status, ("src/styles/custom.css", "custom.css", f"Status {status} is not complete; create next file"))
        path_part, name, reason = next_file
        print(f"CORRECTION: status={status} but model said complete → forcing create_file {path_part}")
        decision = {
            "action": "create_file",
            "file_path": path_part,
            "file_type": "css" if "css" in path_part else "astro_component" if "components" in path_part else "layout",
            "purpose": reason,
            "reasoning": f"Project status is '{status}', not complete. Next: create {name}.",
            "done": False,
        }
        action = "create_file"
    if decision.get("done") and action != "complete":
        decision["done"] = False
    print(f"DECISION: {action} - {decision.get('reasoning', '')[:100]}")

    # Ensure message has a hashable id (add_messages uses m.id as dict key; unhashable id → TypeError)
    out_msg = response
    try:
        if getattr(out_msg, "id", None) is not None:
            hash(out_msg.id)
    except TypeError:
        out_msg = AIMessage(
            content=getattr(response, "content", None) or "",
            id=str(uuid.uuid4()),
            tool_calls=getattr(response, "tool_calls", None) or [],
        )

    return {
        "messages": [out_msg],
        "reasoning_decision": decision,
        "iteration_count": iteration + 1,
        "project_path": project_path,
    }
