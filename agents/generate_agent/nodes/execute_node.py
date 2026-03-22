# nodes/execute_node.py
"""
Execute Node - writes one file per step (write_file_in_site only).
Design context is pre-loaded in state by gather_context + prepare_context.
Execute has exactly one tool: write_file_in_site. After the model calls it, we run it once and the graph goes to analyze (no move_on tool).
"""
import json
import os
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

from agents.generate_agent.state import GenerateAgentState
from agents.generate_agent.utils import (
    get_content_brief,
    get_spec_blocks,
    get_design_spec,
    get_design_brief,
    get_site_target_layout_mandate,
    get_spec_pipeline_mandate,
    format_reasoning_task,
    format_page_brief_for_path,
    normalize_messages_for_api,
)
from agents.generate_agent.llm.tools import get_execute_tools_write_only
from agents.generate_agent.llm.tools.act_tools import set_current_project_path
from agents.generate_agent.llm.chat_factory import get_chat_llm
from agents.generate_agent.nodes.agent_node import get_frontend_design_skill
from agents.generate_agent.spec.utils.llm_image_attachment import (
    merge_bundle_image_urls,
    human_message_text_and_images,
)


# System prompt for execute: role, single tool, quality + frontend philosophy. No ReAct, no shell_execute/write_file/read_file.
EXECUTE_SYSTEM_PROMPT = """====================================================================
ROLE: EXECUTE (write exactly one file)
====================================================================
You are the execution phase. Reasoning already decided WHICH file to create; you only write it.
All context is in the next message: PROJECT STEP (ТЗ from reasoning), CONTENT BRIEF, DESIGN BRIEF, DESIGN CONTEXT FOR THIS FILE, LOADED CONTEXT (skills). Use only that — no documentation search, no extra tools.

YOUR ONLY TOOL: write_file_in_site(path, content)
- Paths are relative to the site/ project directory (e.g. src/components/Hero.astro).
- Call it once per step, for the file path from PROJECT STEP only.

RULES:
- CONTENT BRIEF: ALL headings, titles, body text, CTAs MUST come from it. No generic placeholders.
- DESIGN BRIEF / DESIGN CONTEXT: use PALETTE hex, TYPOGRAPHY fonts, SECTIONS order, BACKGROUNDS and ANIMATIONS as described.
- If the user message contains "USER REFERENCE IMAGES": embed every listed https URL in the file you write (<img src="…" /> or <Image src="…" /> with that exact URL). Never skip them for decorative text-only layouts.
- SECTION COMPOSITION: Each section distinct — asymmetric grids, varied heights, one focal point. No cookie-cutter layout.
- ONE FILE PER STEP: create only the file from PROJECT STEP. Call write_file_in_site once, now.

CRITICAL ASTRO RULES:
1. CSS in frontmatter: import '../styles/custom.css'; NOT <link>
2. Component import: import Hero from '../components/Hero.astro';
3. Only real Tailwind classes: bg-slate-900, text-amber-50 — NOT bg-cream
4. custom.css: PLAIN CSS only (no @apply). Tailwind in .astro HTML.
5. Layout MUST import custom.css (NEVER global.css — always name the file custom.css, never global.css).
6. Deploy-safe URLs (ANY page you generate — not only /history):
   - Site may live at https://automatoria.ru/{repo}/ (subpath). NEVER use root-absolute hrefs: href="/foo", href="/a/b".
   - For EVERY internal link (<a>, <form action> to same site, redirects to internal routes): use withBase.
   - import { withBase } from '../utils/withBase' — adjust depth: src/components/ and src/pages/* → '../utils/withBase'; src/pages/nested/* → '../../utils/withBase'; deeper → more '../'.
   - withBase('') = home; withBase('history') = history route; withBase('operation-detail') = detail; for nested file src/pages/blog/tag.astro use withBase('blog/tag').
   - Only path segments, no leading slash in the argument. External https:// links stay plain strings.
   - astro.config has trailingSlash: 'always' + base from init — withBase adds trailing slash so static hosts serve */history/index.html.

====================================================================
QUALITY MANIFESTO
====================================================================
FORBIDDEN: generic design — bg-gray-200 lists, boring headings, standard forms, cramming sections into index.astro, plain rounded buttons.
MANDATORY: bold color schemes (amber-900, rose-600, emerald-500), custom classes from custom.css in components (.floating, .grain-overlay), overlapping elements, asymmetric grids, 3–5 @keyframes in custom.css.
Ask: "If I see this site in a year, will I remember it?" If NO → make it bolder.

====================================================================
FRONTEND DESIGN PHILOSOPHY
====================================================================
Goal: DISTINCTIVE, production-grade interfaces. Every site UNFORGETTABLE.

TYPOGRAPHY: Unique fonts (NOT Inter/Roboto/Arial). Pair display + body. Google Fonts via <link> in BaseLayout.
COLOR & THEME: Cohesive CSS variables. Real Tailwind used creatively (slate-900, amber-50, rose-600, etc.).
MOTION: Custom @keyframes, staggered reveals, hover surprises, grain overlays, floating elements.
SPATIAL COMPOSITION: Asymmetry, overlap, grid-breaking, generous negative space or controlled density.
BACKGROUNDS: Gradient meshes, noise, geometric patterns, layered transparencies, dramatic shadows.

NEVER: Inter, Roboto, Arial, purple gradients on white, predictable layouts, overused Space Grotesk.
Match complexity to vision: maximalist → elaborate animations; minimalist → restraint and precision.

====================================================================
Execute exactly ONE file from PROJECT STEP. Call write_file_in_site(path, content) now.
"""


def _get_execute_llm():
    """LLM for execute phase (OpenRouter)."""
    model = os.getenv("EXECUTE_MODEL") or os.getenv("OPENROUTER_MODEL")
    return get_chat_llm(model=model, temperature=0.85, parallel_tool_calls=False)


_execute_tools = None
_execute_tools_by_name = None
_execute_llm_with_tools = None


def _get_execute_llm_with_tools():
    global _execute_tools, _execute_tools_by_name, _execute_llm_with_tools
    if _execute_llm_with_tools is None:
        _execute_tools = get_execute_tools_write_only()
        _execute_tools_by_name = {t.name: t for t in _execute_tools}
        _execute_llm_with_tools = _get_execute_llm().bind_tools(_execute_tools, tool_choice="auto")
    return _execute_llm_with_tools, _execute_tools, _execute_tools_by_name


def _normalize_path(p: str) -> str:
    """Normalize path for comparison: strip, no leading slash, forward slashes."""
    if not p or not isinstance(p, str):
        return ""
    return p.strip().replace("\\", "/").lstrip("/")


def _openai_content_block_str(b) -> str:
    """Text or image URL from one multimodal block (OpenAI-style list content)."""
    if not isinstance(b, dict):
        return str(b)
    if b.get("type") == "text" or "text" in b:
        return str(b.get("text") or "")
    if b.get("type") == "image_url":
        iu = b.get("image_url")
        if isinstance(iu, dict):
            return str(iu.get("url") or "")
        return str(iu or "")
    return str(b)


def _message_content_chars(msg) -> int:
    """Length of textual content for one LangChain message (for execute input size logging)."""
    c = getattr(msg, "content", None) or ""
    if isinstance(c, list):
        c = " ".join(_openai_content_block_str(b) for b in c)
    return len(str(c))


def _messages_total_input_chars(msgs: list) -> int:
    """Sum of message content character lengths sent to the execute LLM."""
    return sum(_message_content_chars(m) for m in msgs)


def _run_execute_tools(
    tool_calls: list,
    handle_errors: bool = True,
    allowed_write_path: str | None = None,
) -> list[ToolMessage]:
    """Run execute-phase tools. Only one file per step: write_file_in_site allowed only for allowed_write_path."""
    _, _, tools_by_name = _get_execute_llm_with_tools()
    result_messages = []
    for tc in tool_calls:
        name = tc.get("name")
        args = tc.get("args") or {}
        tid = tc.get("id") or ""
        tool = tools_by_name.get(name)
        if not tool:
            content = f"Tool '{name}' not found."
            result_messages.append(ToolMessage(content=content, tool_call_id=tid))
            continue
        if name == "write_file_in_site" and allowed_write_path is not None:
            call_path = _normalize_path(args.get("path") or "")
            allowed = _normalize_path(allowed_write_path)
            if allowed and call_path != allowed:
                result_messages.append(
                    ToolMessage(
                        content=f"Refused: this step may only write ONE file: {allowed_write_path}. You requested: {args.get('path')}.",
                        tool_call_id=tid,
                    )
                )
                continue
        try:
            content = tool.invoke(args)
            if not isinstance(content, str):
                content = str(content)
            result_messages.append(ToolMessage(content=content, tool_call_id=tid))
        except Exception as e:
            content = f"Error: {e}" if handle_errors else str(e)
            result_messages.append(ToolMessage(content=content, tool_call_id=tid))
    return result_messages


def _execute_node(state: GenerateAgentState) -> dict:
    """
    Execute node: one tool (write_file_in_site). One invoke, one tool run; after write the graph goes to analyze.
    """
    decision = state.get("reasoning_decision", {})
    project_path = state.get("project_path", "/path/to/site")
    loaded_skills_context = state.get("loaded_skills_context") or ""
    step_design_summary = state.get("step_design_summary") or ""

    # Tell write_file_in_site where to write files for this run
    set_current_project_path(project_path)

    if not decision:
        return {"messages": []}

    if decision.get("action") == "complete" or decision.get("done"):
        from langchain_core.messages import AIMessage
        return {"messages": [AIMessage(content="PROJECT COMPLETE")]}

    file_path_raw = decision.get("file_path") or ""
    file_path_lower = file_path_raw.lower()
    is_ui_task = (
        decision.get("action") == "create_file"
        and any(x in file_path_lower for x in [".astro", "custom.css", "global.css", "styles/", "components/", "layouts/", "pages/"])
    )
    system_content = EXECUTE_SYSTEM_PROMPT
    has_loaded_context = bool((loaded_skills_context or "").strip())
    if is_ui_task and not has_loaded_context:
        full_skill = get_frontend_design_skill()
        system_content += "\n\n=== FRONTEND-DESIGN SKILL (MANDATORY FOR THIS FILE) ===\n" + full_skill + "\n=== END SKILL ===\n"

    # Execute receives ONLY: spec_mandate + content_brief + design_brief + step_design_summary + loaded_skills_context + ТЗ (task_desc + decision). No other messages.
    content_brief = get_content_brief(state)
    arch_blocks = get_spec_blocks(state)
    design_spec = get_design_spec(state)
    site_target_block = get_site_target_layout_mandate(state)
    spec_mandate = get_spec_pipeline_mandate(state)
    content_block = ""
    if site_target_block:
        content_block += site_target_block + "\n"
    if spec_mandate:
        content_block += spec_mandate + "\n"
    ppc = (state.get("page_plan_context") or "").strip()
    if ppc:
        content_block += ppc + "\n\n"
    if content_brief or arch_blocks:
        content_block += """
=== CONTENT BRIEF (MANDATORY for all copy: headings, body, CTAs — use ONLY this text, no generic placeholders) ===
""" + (content_brief or "")
        if arch_blocks:
            content_block += "\nBlocks: " + ", ".join(str(b.get("type", "")) for b in arch_blocks[:8])
        content_block += "\n=== END CONTENT BRIEF ===\n\n"
    design_brief_full = get_design_brief(state)
    if design_brief_full:
        content_block += "\n=== FULL DESIGN BRIEF (section concepts, UI Kit, animations — follow for styles and components) ===\n" + design_brief_full[:8000] + "\n=== END DESIGN BRIEF ===\n\n"
    elif design_spec:
        content_block += """
=== DESIGN (from planning — palette, typography, mood; follow for styles and components) ===
"""
        if design_spec.get("palette"):
            content_block += f"Palette: {design_spec.get('palette')}\n"
        if design_spec.get("typography"):
            content_block += f"Typography: {design_spec.get('typography')}\n"
        if design_spec.get("mood"):
            content_block += f"Mood: {design_spec.get('mood')}\n"
        if design_spec.get("key_requirements"):
            reqs = design_spec.get("key_requirements", [])
            content_block += "Key requirements: " + "; ".join(str(r) for r in reqs) + "\n"
        content_block += "=== END DESIGN ===\n\n"
    fp_ctx = (decision.get("file_path") or "").strip()
    if fp_ctx and "pages/" in fp_ctx.lower() and fp_ctx.lower().endswith(".astro"):
        pb_one = format_page_brief_for_path(state, fp_ctx)
        if pb_one:
            content_block += (
                "\n=== PAGE BRIEF (Phase 1 — this route only; follow for structure and copy) ===\n"
                + pb_one
                + "\n=== END PAGE BRIEF ===\n\n"
            )
    task_instruction = "Call write_file_in_site(path, content) for the file in PROJECT STEP. Do it now."
    task_desc = format_reasoning_task(decision, project_path)
    step_design_block = ""
    if step_design_summary.strip():
        step_design_block = f"\n{step_design_summary.strip()}\n\n"
    loaded_block = ""
    if loaded_skills_context.strip():
        loaded_block = f"""
=== LOADED CONTEXT (guidelines and file contents for this step) ===
{loaded_skills_context.strip()}
=== END LOADED CONTEXT ===

"""
    execute_context = f"""
{task_desc}
{content_block}{step_design_block}{loaded_block}Full decision (JSON): {json.dumps(decision, indent=2, ensure_ascii=False)}

PROJECT_PATH: {project_path}

TASK: {task_instruction}
Use PROJECT STEP (ТЗ from reasoning) + CONTENT BRIEF + DESIGN BRIEF + DESIGN CONTEXT FOR THIS FILE + LOADED CONTEXT (skills). Call write_file_in_site now.
"""
    jd_raw = state.get("json_data")
    jd = jd_raw if isinstance(jd_raw, dict) else {}
    human_msg = human_message_text_and_images(
        execute_context, merge_bundle_image_urls(jd)
    )
    messages = [SystemMessage(content=system_content), human_msg]
    messages = normalize_messages_for_api(messages)

    sys_chars = len(system_content)
    human_chars = _message_content_chars(human_msg)
    total_chars = _messages_total_input_chars(messages)
    print(
        f"EXECUTE_LLM input: total_chars={total_chars} "
        f"(system_chars={sys_chars}, human_execute_context_chars={human_chars}, msgs_count={len(messages)})",
        flush=True,
    )

    allowed_path = None
    if decision.get("action") == "create_file":
        allowed_path = (decision.get("file_path") or "").strip().lstrip("/")
        if allowed_path and not allowed_path.startswith("src/"):
            allowed_path = "src/" + allowed_path

    exec_llm, _, _ = _get_execute_llm_with_tools()
    new_messages: list = []
    response = exec_llm.invoke(messages)
    new_messages.append(response)
    if getattr(response, "tool_calls", None):
        tool_results = _run_execute_tools(
            response.tool_calls,
            handle_errors=True,
            allowed_write_path=allowed_path,
        )
        new_messages.extend(tool_results)
    else:
        # No tool call: nudge to call write_file_in_site
        if decision.get("action") == "create_file":
            nudge = f'You must call write_file_in_site(path, content) for: {decision.get("file_path", "")}.'
            nudge_msgs = normalize_messages_for_api(
                messages + new_messages + [HumanMessage(content=nudge)]
            )
            nudge_total = _messages_total_input_chars(nudge_msgs)
            print(
                f"EXECUTE_LLM nudge invoke: total_chars={nudge_total} (msgs_count={len(nudge_msgs)})",
                flush=True,
            )
            response2 = exec_llm.invoke(nudge_msgs)
            new_messages.append(response2)
            if getattr(response2, "tool_calls", None):
                tool_results = _run_execute_tools(
                    response2.tool_calls,
                    handle_errors=True,
                    allowed_write_path=allowed_path,
                )
                new_messages.extend(tool_results)
    return {"messages": new_messages}
