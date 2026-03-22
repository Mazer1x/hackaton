"""PascalCase Astro component filenames from section ids (LLM may add punctuation, parens, &)."""
from __future__ import annotations

import re


def pascal_case_component_basename(section_key: str) -> str:
    """
    One PascalCase name: take only [a-z0-9]+ tokens from the key, capitalize each, join.
    Matches files like HeroGuideTitleIntroduction.astro when outline was
    "Hero (Guide Title & Introduction)" → id hero_(guide_title_&_introduction).
    """
    raw = (section_key or "").strip()
    tokens = re.findall(r"[a-z0-9]+", raw.lower())
    if not tokens:
        return "Section"
    return "".join(t.capitalize() for t in tokens)


def component_filename_from_section_key(section_key: str) -> str:
    """e.g. hero_guide / hero_(foo&bar) → HeroGuide.astro / HeroFooBar.astro"""
    return f"{pascal_case_component_basename(section_key)}.astro"
