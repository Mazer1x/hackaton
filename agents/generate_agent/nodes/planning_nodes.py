# nodes/planning_nodes.py
"""
Planning subgraph: generate DESIGN for the site from JSON brief + user description.
Outputs project_spec with design, design_brief, short_summary, content_brief, sections, blocks (JSON only, no tools).
"""
import json
import os
from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage

from agents.generate_agent.state import GenerateAgentState
from agents.generate_agent.utils import (
    get_user_request,
    build_content_brief,
    build_short_site_info,
)
from agents.generate_agent.llm.chat_factory import get_chat_llm


# ТЗ-only skills: llm/skills/planning/; frontend skills: llm/skills/frontend/
PLANNING_SKILLS_DIR = "planning"
FRONTEND_SKILLS_DIR = "frontend"


def _get_planning_skills_block() -> str:
    """Build system block for planning: ТЗ from skills/planning/, frontend from skills/frontend/."""
    base = Path(__file__).resolve().parent.parent / "llm" / "skills"
    block_parts = []
    # ТЗ-only: read from planning/ (not visible to load_skill)
    for name, label in [
        ("design-brief", "DESIGN BRIEF (structure for design_brief field)"),
        ("design-generation", "DESIGN GENERATION (concrete palette, typography, motion)"),
    ]:
        path = base / PLANNING_SKILLS_DIR / f"{name}.md"
        if path.is_file():
            content = path.read_text(encoding="utf-8").strip()
            block_parts.append(f"=== {label} ===\n\n{content}\n\n=== END {label} ===")
    # Frontend: read from skills/frontend/
    for name, label in [
        ("frontend-astro", "FRONTEND ASTRO (structure, styles order, components)"),
        ("frontend-design", "FRONTEND DESIGN (aesthetics, bold choices)"),
    ]:
        path = base / FRONTEND_SKILLS_DIR / f"{name}.md"
        if path.is_file():
            content = path.read_text(encoding="utf-8").strip()
            block_parts.append(f"=== {label} ===\n\n{content}\n\n=== END {label} ===")
    return "\n\n".join(block_parts) if block_parts else ""


PLANNING_PROMPT = """You are the PLANNING module of a Frontend Builder Agent.

Your task: generate a DESIGN for the site based on:
1) The JSON BRIEF below (brand, business, goals, content) — use it as the main source of truth.
2) The USER DESCRIPTION (if any) — additional wishes, style, or constraints.

You do NOT write code. Reason about the brief, then output ONE JSON object.

Consider:
- What does the JSON say about brand, tone, audience, CTA?
- What visual style fits: colors, typography, mood (e.g. bold, minimal, warm, tech)?
- What sections and content do we need from the brief?
- What distinctive design elements (animations, layout, palette) will make the site stand out?

Output a single JSON object with these keys:

{
  "short_summary": "1-3 sentences: theme, brand/goal, main CTA (for reasoning/load_skills)",
  "content_brief": "Full text for the site from the JSON + your wording: headings, section titles, body, CTAs. No placeholders — concrete text for the builder.",
  "sections": ["Hero", "About", "Services", "Contact"],
  "blocks": [
    {"type": "hero", "content": {"headline": "...", "subheadline": "...", "cta": "..."}},
    {"type": "about", "content": {"title": "...", "body": "..."}}
  ],
  "design": {
    "palette": "e.g. slate-900 bg, amber-500 accent, stone-100 text; or: dark theme with emerald accents",
    "typography": "e.g. Playfair Display for headings, Inter for body; or: bold sans + serif accent",
    "mood": "e.g. bold, minimal, warm, tech, editorial",
    "key_requirements": ["custom.css animations", "grain or gradient overlay", "floating elements", "distinctive CTA button"]
  },
  "design_brief": "Optional. Full design concept in markdown: use the structure from the DESIGN BRIEF skill below."
}

Rules:
- short_summary: brief for the agent. Max ~400 chars.
- content_brief: take content FROM THE JSON BRIEF; rephrase if needed. Execute phase will use ONLY this text.
- sections / blocks: structure from the brief + user description.
- design: MUST be filled. palette, typography, mood, key_requirements.
- design_brief: RECOMMENDED. Use the DESIGN BRIEF skill structure below. Put the whole markdown string in this field (escape newlines as \\n if needed in JSON).
- design: Follow the DESIGN GENERATION skill for concrete palette, typography, key_requirements. Follow FRONTEND ASTRO for file/structure hints and FRONTEND DESIGN for aesthetic direction.

Output: JSON object only (no markdown, no explanation)."""


def _get_planning_llm():
    """LLM for planning (OpenRouter); no tools, JSON output only."""
    model = os.getenv("REASONING_MODEL") or os.getenv("OPENROUTER_MODEL")
    return get_chat_llm(model=model, temperature=0.4, parallel_tool_calls=False)


def _planning_node(state: GenerateAgentState) -> dict:
    """
    Planning node: generate DESIGN (and full ТЗ) from json_data + user description.
    Outputs JSON only; we parse and set project_spec.
    """
    messages = state.get("messages", [])
    user_request = get_user_request(messages)
    json_data = state.get("json_data") or {}
    site_architecture = state.get("site_architecture") or {}

    # Run planning if we have JSON brief and/or user description
    has_json = bool(json_data and isinstance(json_data, dict))
    has_user = bool(user_request and user_request.strip())
    if not has_json and not has_user:
        return {"project_spec": None}

    content_brief_from_json = build_content_brief(json_data) if has_json else ""
    short_from_json = build_short_site_info(json_data) if has_json else ""
    arch_sections = site_architecture.get("sections", [])
    arch_blocks = site_architecture.get("blocks", [])

    json_block = ""
    if has_json:
        json_block = """
=== JSON BRIEF (brand, business, content — use this for content_brief and design) ===
"""
        if short_from_json:
            json_block += f"Summary: {short_from_json}\n\n"
        if content_brief_from_json:
            json_block += content_brief_from_json + "\n\n"
        if arch_sections:
            json_block += f"Sections (order): {', '.join(arch_sections)}\n"
        if arch_blocks:
            json_block += "Blocks: " + ", ".join(str(b.get("type", "")) for b in arch_blocks[:10]) + "\n"
        json_block += "=== END JSON BRIEF ===\n\n"

    user_block = ""
    if has_user:
        user_block = f"=== USER DESCRIPTION ===\n{user_request.strip()}\n=== END USER DESCRIPTION ===\n\n"

    skills_block = _get_planning_skills_block()
    system_content = PLANNING_PROMPT
    if skills_block:
        system_content += "\n\n" + skills_block

    planning_llm = _get_planning_llm()
    human_content = f"""{json_block}{user_block}Generate the site DESIGN from the JSON brief above and the user description (if any). Output the final JSON with short_summary, content_brief, sections, blocks, design, and (recommended) design_brief, following the skills above (design-brief structure, design-generation for concrete design, frontend-astro for structure, frontend-design for aesthetics)."""

    prompt_messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=human_content),
    ]
    response = planning_llm.invoke(prompt_messages)

    content = (response.content or "").strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    content = content.strip()

    spec = None
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            design_raw = data.get("design")
            design = design_raw if isinstance(design_raw, dict) else {}
            design_brief_raw = data.get("design_brief")
            design_brief = (design_brief_raw or "").strip() if isinstance(design_brief_raw, str) else ""
            spec = {
                "short_summary": (data.get("short_summary") or "").strip(),
                "content_brief": (data.get("content_brief") or "").strip(),
                "sections": data.get("sections") if isinstance(data.get("sections"), list) else [],
                "blocks": data.get("blocks") if isinstance(data.get("blocks"), list) else [],
                "design": design,
                "design_brief": design_brief,
            }
            print(f"Planning: ТЗ ready — sections={spec.get('sections')}, design={bool(spec.get('design'))}, design_brief={bool(spec.get('design_brief'))}, brief_len={len(spec.get('content_brief', ''))}")
    except json.JSONDecodeError as e:
        print(f"Planning: failed to parse JSON spec: {e}. Continuing without project_spec.")

    return {
        "messages": [response],
        "project_spec": spec,
    }


def _should_continue_planning(state: GenerateAgentState) -> str:
    """After planning: always → init_project (then analyze). No tools."""
    return "init_project"
