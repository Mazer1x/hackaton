"""Load skill .md files from spec/skills."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from agents.generate_agent.spec.config import SKILLS_DIR, KNOWLEDGE_DIR


@dataclass
class ParsedSkill:
    name: str
    description: str
    system_prompt: str
    user_prompt_template: str
    quality_checks: list[str]
    raw: str = ""

    def format_user_prompt(self, **kwargs: object) -> str:
        text = self.user_prompt_template
        for k, v in kwargs.items():
            text = text.replace(f"{{{k}}}", str(v))
        return text


def _extract_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
    return meta, m.group(2)


def _extract_code_block(text: str, header: str) -> str:
    pattern = re.compile(
        rf"###?\s*{re.escape(header)}.*?```[^\n]*\n(.*?)```",
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def _extract_quality_checks(text: str) -> list[str]:
    checks: list[str] = []
    for m in re.finditer(r"-\s*\[[ x]]\s*(.+)", text):
        checks.append(m.group(1).strip())
    return checks


def load_skill(name: str) -> ParsedSkill:
    if not name.endswith(".md"):
        name += ".md"
    path = SKILLS_DIR / name
    raw = path.read_text(encoding="utf-8")
    meta, body = _extract_frontmatter(raw)
    return ParsedSkill(
        name=meta.get("name", path.stem),
        description=meta.get("description", ""),
        system_prompt=_extract_code_block(body, "System Prompt"),
        user_prompt_template=_extract_code_block(body, "User Prompt"),
        quality_checks=_extract_quality_checks(body),
        raw=raw,
    )


def load_knowledge(name: str) -> str:
    if not name.endswith(".md"):
        name += ".md"
    return (KNOWLEDGE_DIR / name).read_text(encoding="utf-8")
