"""
Make plan node: LLM builds ordered list of files to generate (generation_plan).
Check_plan then does physical existence check (no AI).
"""
import json
import os
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage

from agents.generate_agent.state import GenerateAgentState
from agents.generate_agent.utils import get_content_brief, get_spec_sections, get_spec_blocks
from agents.generate_agent.llm.chat_factory import get_chat_llm
from agents.generate_agent.spec.utils.site_pages import expected_page_paths


MAKE_PLAN_PROMPT = """You are the planner for a Frontend Builder. Your ONLY job is to output a JSON object with one key: "generation_plan".

"generation_plan" must be an ordered list of file paths (strings) that will be created for the site. Rules:
1. Paths are relative to the project root. Use forward slashes. Example: "src/styles/custom.css", "src/layouts/BaseLayout.astro".
2. Order is fixed: first custom.css, then BaseLayout.astro, then one .astro file per section/component (in the order given in the brief or layout_spec), then ALL page files (single-page: only index.astro; multi-page: index.astro plus e.g. src/pages/about.astro, src/pages/schedule.astro).
3. Styles: exactly one entry: "src/styles/custom.css".
4. Layout: exactly one: "src/layouts/BaseLayout.astro".
5. Components: one per section. Path format: "src/components/<Name>.astro". Name in PascalCase (e.g. Hero, About, Services, ContactForm).
6. Pages: one entry per route — always "src/pages/index.astro" for home; for additional routes use kebab-case filenames (e.g. src/pages/schedule.astro).

Output ONLY valid JSON, no markdown, no explanation. Example (single-page):
{"generation_plan": ["src/styles/custom.css", "src/layouts/BaseLayout.astro", "src/components/Hero.astro", "src/components/About.astro", "src/components/Services.astro", "src/pages/index.astro"]}
Multi-page example:
{"generation_plan": ["src/styles/custom.css", "src/layouts/BaseLayout.astro", "src/components/Hero.astro", "src/pages/index.astro", "src/pages/rules.astro"]}
"""


def _fallback_plan(state: GenerateAgentState) -> list[str]:
    """Rule-based fallback when LLM fails or returns invalid plan."""
    plan = ["src/styles/custom.css", "src/layouts/BaseLayout.astro"]
    layout_spec = state.get("layout_spec") or {}
    project_spec = state.get("project_spec") or {}
    sections = layout_spec.get("sections") or project_spec.get("sections") or []
    if sections:
        seen = set()
        for sec in sections:
            raw = (sec if isinstance(sec, dict) else {}).get("id") or (sec if isinstance(sec, dict) else {}).get("role") or "section"
            s = str(raw).strip().replace("-", " ").replace("_", " ")
            name = "".join(w.capitalize() for w in s.split()) or "Section"
            if name and name not in seen:
                seen.add(name)
                plan.append(f"src/components/{name}.astro")
    else:
        for name in ["Hero", "About", "Services"]:
            plan.append(f"src/components/{name}.astro")
    canonical = state.get("canonical_spec") or {}
    ids = canonical.get("pages") if isinstance(canonical.get("pages"), list) else None
    if ids:
        for p in expected_page_paths([str(x).strip() for x in ids if str(x).strip()]):
            if p not in plan:
                plan.append(p)
    else:
        plan.append("src/pages/index.astro")
    return plan


def _validate_plan(plan: list) -> list[str]:
    """Keep only paths that look like src/... .css or src/... .astro."""
    out = []
    for p in plan:
        if not isinstance(p, str):
            continue
        p = p.strip().replace("\\", "/")
        if p.startswith("src/") and (p.endswith(".css") or p.endswith(".astro")):
            out.append(p)
    return out


def make_plan_node(state: GenerateAgentState) -> dict:
    """
    LLM builds generation_plan from layout_spec / project_spec / content brief.
    Fallback: rule-based plan. check_plan (no AI) will then verify which files exist.
    """
    layout_spec = state.get("layout_spec") or {}
    project_spec = state.get("project_spec") or {}
    content_brief = get_content_brief(state)
    arch_sections = get_spec_sections(state)
    arch_blocks = get_spec_blocks(state)
    site_info = state.get("site_info") or ""

    sections_json = ""
    if layout_spec.get("sections"):
        sections_json = json.dumps([s if isinstance(s, dict) else {"id": str(s)} for s in layout_spec["sections"]], ensure_ascii=False, indent=2)
    elif project_spec.get("sections"):
        sections_json = json.dumps(project_spec["sections"], ensure_ascii=False, indent=2)
    elif arch_sections:
        sections_json = json.dumps(arch_sections, ensure_ascii=False)

    user_content = f"""Site / goal: {site_info}

Content brief (use this to derive section/component names and order):
{content_brief or "(none)"}

Sections from spec (order and ids/roles for component names):
{sections_json or "(none — use default: Hero, About, Services)"}

Blocks hint: {", ".join(str(b.get("type", "")) for b in (arch_blocks or [])[:10]) or "(none)"}

Output JSON with key "generation_plan": ordered list of file paths. Only valid JSON, no markdown."""

    model = os.getenv("REASONING_MODEL") or os.getenv("OPENROUTER_MODEL")
    llm = get_chat_llm(model=model, temperature=0.3, parallel_tool_calls=False)
    try:
        response = llm.invoke([SystemMessage(content=MAKE_PLAN_PROMPT), HumanMessage(content=user_content)])
        content = (response.content or "").strip()
        if "```" in content:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            else:
                content = content.split("```")[1].split("```")[0]
        data = json.loads(content)
        plan = data.get("generation_plan")
        if isinstance(plan, list) and plan:
            plan = _validate_plan(plan)
            if plan:
                print(f"MAKE_PLAN (LLM): {len(plan)} files: {plan}")
                return {"generation_plan": plan}
    except Exception as e:
        print(f"MAKE_PLAN LLM failed ({e}), using fallback")
    plan = _fallback_plan(state)
    print(f"MAKE_PLAN (fallback): {len(plan)} files: {plan}")
    return {"generation_plan": plan}
