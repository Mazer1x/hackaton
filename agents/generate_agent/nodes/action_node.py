# nodes/action_node.py
"""
Action Node - uses Claude Sonnet 4 for ACT (code generation).
Receives decision from reasoning node and executes it (writes code, calls tools).
"""
import os
from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from agents.generate_agent.llm.chat_factory import get_chat_llm

from agents.generate_agent.state import GenerateAgentState
from agents.generate_agent.utils import get_user_request, get_content_brief, get_spec_blocks, get_design_spec, get_design_brief, normalize_messages_for_api
from agents.generate_agent.llm.tools import get_base_tools


# Import DESIGN PHILOSOPHY and skill loader from agent_node
from agents.generate_agent.nodes.agent_node import SYSTEM_PROMPT, get_frontend_design_skill


ACTION_PROMPT = """You are the ACTION module of an autonomous Frontend Builder Agent.

Your task: ACT - generate CODE based on reasoning model's decision!

You receive a structured decision about WHAT needs to be created.
Your task - create it with MAXIMUM creativity and quality.

CRITICAL RULES FOR ASTRO:

1. CSS import in frontmatter:
   WRONG: <link rel="stylesheet" href="/src/styles/custom.css">
   CORRECT: import '../styles/custom.css'; in frontmatter

2. Component import:
   CORRECT: import Hero from '../components/Hero.astro';
   CORRECT: import BaseLayout from '../layouts/BaseLayout.astro';

3. ONLY real Tailwind classes:
   CORRECT: bg-slate-900, text-amber-50, border-lime-500
   WRONG: bg-cream, text-ink, bg-brown (don't exist!)

4. Tailwind v4 (BUILD MUST SUCCEED ON FIRST TRY):
   WRONG: @apply in custom.css (causes "unknown utility class" in v4)
   CORRECT: In custom.css use PLAIN CSS only (no @apply). Use Tailwind classes in .astro HTML.
   WRONG: Layout imports only custom.css
   CORRECT: Layout MUST import global.css first (Tailwind), then custom.css:
     import '../styles/global.css';
     import '../styles/custom.css';

""" + SYSTEM_PROMPT + """

===================================================================
SKILLS SYSTEM (Progressive Disclosure)
===================================================================

You have access to specialized skills through tools:

load_skill(skill_name) - Load detailed instructions for task
  Available skills:
  • frontend-design: Detailed guidelines for DISTINCTIVE UI design
  • astro-expert: Best practices for Astro (coming soon)
  • tailwind-wizard: Advanced Tailwind patterns (coming soon)

list_skills() - Show all available skills

WHEN TO LOAD SKILLS:
- When creating UI components → load_skill("frontend-design")
- When detailed design instructions needed
- When specialized knowledge required

WORKFLOW:
1. If skill needed - call load_skill("skill_name")
2. After loading - CONTINUE work in same request
3. Use loaded instructions for code generation
4. Call write_file with code

Progressive Disclosure: Skills are loaded ONLY when needed!
   This saves tokens and speeds up work.
   
IMPORTANT: If you already called load_skill and got result in messages,
   DON'T call it again! Use received instructions and generate code!

===================================================================
YOUR TASK
===================================================================

You will receive JSON with decision:
{
  "action": "create_file",
  "file_path": "/src/components/Hero.astro",
  "file_type": "astro_component",
  "purpose": "Hero section with bold typography",
  "key_requirements": ["Google Fonts", "text-7xl+", "floating elements"],
  "reasoning": "First section must be UNFORGETTABLE"
}

Your task:
1. EVALUATE task - is skill needed for detailed instructions?
   → If creating UI component: load_skill("frontend-design")
2. READ requirements carefully
3. CREATE distinctive code (NOT generic!)
4. USE write_file to create file

CRITICAL:
- You WRITE CODE, not reason
- Follow key_requirements exactly
- Create BOLD, DISTINCTIVE design (from SYSTEM_PROMPT + skills)
- Use write_file or shell_execute tools
- DON'T create generic bg-gray-200 code!
- Load skills when detailed instructions needed!

If action = "create_file" → load_skill if needed, then write_file with code
If action = "shell_command" → shell_execute
If action = "complete" → say "PROJECT COMPLETE"
"""


def _get_action_llm():
    """Create LLM for action (OpenRouter)."""
    model = os.getenv("EXECUTE_MODEL") or os.getenv("OPENROUTER_MODEL")
    return get_chat_llm(model=model, temperature=0.85, parallel_tool_calls=False)


# Initialize tools
_tools = get_base_tools()

_action_llm = _get_action_llm()
_action_llm_with_tools = _action_llm.bind_tools(_tools, tool_choice="auto")


def _action_node(state: GenerateAgentState) -> dict:
    """
    Action Node: receives decision from reasoning and executes it.
    Uses Claude Sonnet 4 (more expensive, but more creative).
    
    IMPORTANT: Can be called twice:
    1. First time: receives decision, may call load_skill
    2. Second time: receives load_skill result, generates code with write_file
    """
    import json
    
    decision = state.get("reasoning_decision", {})
    project_path = state.get("project_path", "/path/to/site")
    requirements = state.get("requirements", {})
    design_tokens = state.get("design_tokens", {})
    existing_messages = state.get("messages", [])
    
    if not decision:
        print("No decision from reasoning node!")
        return {"messages": []}
    
    action = decision.get("action")
    
    # If project complete - don't call action model
    if action == "complete" or decision.get("done"):
        from langchain_core.messages import AIMessage
        return {
            "messages": [AIMessage(content="PROJECT COMPLETE")]
        }
    
    # CHECK: Is this repeat call after load_skill?
    # If messages has ToolMessage with load_skill result, use ALL messages
    has_tool_result = False
    for msg in reversed(existing_messages):
        if hasattr(msg, "name") and msg.name in ["load_skill", "list_skills"]:
            has_tool_result = True
            print(f"ACTION repeat call: detected result from {msg.name}")
            break
    
    if has_tool_result:
        # Repeat call - use existing_messages as is
        # (SystemMessage should already be at start)
        messages = existing_messages
        print("ACTION continues work with loaded skill...")
        
        # Check that SystemMessage is at start, if not - add it
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=ACTION_PROMPT)] + messages
    else:
        # First call - form new context (include user request + ТЗ or json_data + FULL SKILL for UI)
        user_request = get_user_request(state.get("messages", []))
        content_brief = get_content_brief(state)
        arch_blocks = get_spec_blocks(state)

        # Inject FULL frontend-design skill when creating UI files (so design is bold, not generic)
        file_path_raw = decision.get("file_path") or ""
        file_path = file_path_raw.lower()
        is_ui_task = (
            decision.get("action") == "create_file"
            and any(x in file_path for x in [".astro", "custom.css", "global.css", "styles/", "components/", "layouts/", "pages/"])
        )
        skill_block = ""
        full_skill_text = ""  # reused for system message when is_ui_task
        if is_ui_task:
            full_skill_text = get_frontend_design_skill()
            print(f"[ACTION] Injecting frontend-design skill (file={file_path_raw}, skill_len={len(full_skill_text)})")
            # Short checklist FIRST — model must satisfy these; then full skill
            skill_block = f"""
===================================================================
MANDATORY FOR THIS FILE (from frontend-design skill). YOUR CODE MUST:
===================================================================
1. FONT: Use a NAMED non-generic font (e.g. Playfair Display, Cormorant, Bebas Neue) — NOT Inter/Roboto/Arial.
2. COLORS: Use a BOLD palette (e.g. amber-500, emerald-600, blue-800, stone-900) — NOT gray-200 or purple-on-white.
3. DISTINCTIVE ELEMENT: At least one of: custom class from custom.css (.floating, .grain-overlay, .cta-bounce), or @keyframes animation, or asymmetric layout.
4. NO GENERIC AI LOOK: Avoid bg-gray-200 lists, boring rounded buttons, predictable sections. Make it UNFORGETTABLE.

Full skill text below — apply it.
===================================================================
FRONTEND-DESIGN SKILL (FULL)
===================================================================
{full_skill_text}

(custom.css: plain CSS only, no @apply. Tailwind classes in .astro HTML.)
===================================================================
"""
        else:
            print(f"[ACTION] No skill (action={decision.get('action')}, file_path={file_path_raw})")

        content_block = ""
        if content_brief or arch_blocks:
            content_block = """
===================================================================
CONTENT BRIEF (from JSON) — USE THESE TEXTS IN THE SITE! No "Creative Studio", no "Discover Something"!
===================================================================
"""
            if content_brief:
                content_block += content_brief + "\n\n"
            if arch_blocks:
                content_block += "Blocks (use for sections):\n"
                for b in arch_blocks[:12]:
                    content_block += f"  {b.get('type', '')}: {b.get('content', {})}\n"
            content_block += """
Headings, titles, CTAs, descriptions MUST be taken from the brief above (e.g. brand name, tagline, CTA text).
"""
        design_spec = get_design_spec(state)
        design_brief_full = get_design_brief(state)
        design_block = ""
        if design_brief_full:
            design_block = """
===================================================================
FULL DESIGN BRIEF (section concepts, UI Kit, animations — follow for this file)
===================================================================
""" + design_brief_full[:6000] + "\n\n"
        elif design_spec:
            design_block = """
===================================================================
DESIGN (from planning — follow for palette, typography, mood)
===================================================================
"""
            if design_spec.get("palette"):
                design_block += f"Palette: {design_spec.get('palette')}\n"
            if design_spec.get("typography"):
                design_block += f"Typography: {design_spec.get('typography')}\n"
            if design_spec.get("mood"):
                design_block += f"Mood: {design_spec.get('mood')}\n"
            if design_spec.get("key_requirements"):
                reqs = design_spec.get("key_requirements", [])
                design_block += "Key: " + "; ".join(str(r) for r in reqs) + "\n"
            design_block += "\n"
        # Skill block FIRST so model sees mandatory checklist before anything else
        context = f"""
{skill_block}
===================================================================
USER REQUEST (theme / goal)
===================================================================

{user_request or "(build site from content brief below)"}
{content_block}
{design_block}

===================================================================
DECISION FROM REASONING MODEL
===================================================================

{json.dumps(decision, indent=2, ensure_ascii=False)}

PROJECT_PATH: {project_path}

REQUIREMENTS:
{json.dumps(requirements or {}, indent=2, ensure_ascii=False)}

DESIGN TOKENS:
{json.dumps(design_tokens or {}, indent=2, ensure_ascii=False)}

===================================================================
YOUR TASK
===================================================================

EXECUTE this decision. If CONTENT BRIEF is present above — use ONLY that content (no generic placeholders).

If action = "create_file":
→ Your write_file code MUST satisfy the MANDATORY checklist at the top (named font, bold colors, distinctive element, no generic AI look).
→ Call write_file(path=PROJECT_PATH + file_path_raw, content=FULL_CODE)
→ Code must be DISTINCTIVE (follow key_requirements + skill).
→ DON'T write generic bg-gray-200 code!

If action = "shell_command":
→ Call shell_execute(command=..., working_directory=PROJECT_PATH)

ACT NOW! Call needed tool.
"""
        
        # Put skill into SYSTEM message when UI task — models follow system prompt more reliably
        system_content = ACTION_PROMPT
        if is_ui_task and full_skill_text:
            system_content += """

===================================================================
FRONTEND-DESIGN SKILL (IN SYSTEM — MANDATORY FOR THIS REQUEST)
===================================================================
""" + full_skill_text + """

Apply the above in every create_file: named font, bold colors, distinctive element, no generic AI look.
===================================================================
"""
        
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=context)
        ]
    messages = normalize_messages_for_api(messages)

    response = _action_llm_with_tools.invoke(messages)
    
    return {
        "messages": [response]
    }
