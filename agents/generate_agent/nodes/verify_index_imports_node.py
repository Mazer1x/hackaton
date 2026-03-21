# nodes/verify_index_imports_node.py
"""
Проверка: относительные импорты в index.astro → существующие файлы.
Цикл с fix_index_imports_llm: verify → (не OK) → fix → verify → … до OK или лимита попыток.
"""
from __future__ import annotations

import re
from pathlib import Path

from agents.generate_agent.state import GenerateAgentState

_IMPORT_FROM = re.compile(
    r"""from\s+['"](\.\./[^'"]+)['"]""",
    re.MULTILINE,
)

MAX_INDEX_IMPORT_FIX_ATTEMPTS = 5


def _collect_missing_imports(index_file: Path, project_root: Path) -> list[str]:
    if not index_file.is_file():
        return ["src/pages/index.astro"]

    try:
        content = index_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ["src/pages/index.astro"]

    missing: list[str] = []
    seen: set[str] = set()
    pages_dir = index_file.parent.resolve()
    root = project_root.resolve()

    for m in _IMPORT_FROM.finditer(content):
        rel = (m.group(1) or "").strip()
        if not rel.startswith(("./", "../")):
            continue
        target = (pages_dir / rel).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            continue
        key = str(target)
        if key in seen:
            continue
        seen.add(key)
        if not target.is_file():
            try:
                rel_to_root = target.relative_to(root).as_posix()
            except ValueError:
                rel_to_root = str(target)
            missing.append(rel_to_root)

    return missing


def _verify_index_imports_node(state: GenerateAgentState) -> dict:
    """Первый заход с reasoning: сброс счётчика. Повтор после fix: счётчик не трогаем."""
    loop_updates: dict = {}
    if state.get("_verify_after_fix"):
        loop_updates["_verify_after_fix"] = None
    else:
        loop_updates["_index_import_fix_rounds"] = 0

    project_path = (state.get("project_path") or "").strip()
    pa = dict(state.get("project_analysis") or {})

    if not project_path:
        return loop_updates

    root = Path(project_path)
    plan = state.get("generation_plan") or []
    page_paths = [
        root / p
        for p in plan
        if isinstance(p, str) and p.startswith("src/pages/") and p.endswith(".astro")
    ]
    if not page_paths:
        page_paths = [root / "src" / "pages" / "index.astro"]

    missing: list[str] = []
    seen: set[str] = set()
    for page_file in page_paths:
        if not page_file.is_file():
            try:
                rel = page_file.relative_to(root).as_posix()
            except ValueError:
                rel = str(page_file)
            if rel not in seen:
                seen.add(rel)
                missing.append(rel)
            continue
        for m in _collect_missing_imports(page_file, root):
            if m not in seen:
                seen.add(m)
                missing.append(m)

    if not missing:
        print("VERIFY_INDEX_IMPORTS: OK — импорты во всех страницах из плана резолвятся в файлы.")
        pa = {
            **pa,
            "index_imports_verified": True,
            "missing_index_imports": [],
        }
        return {**loop_updates, "project_analysis": pa}

    print(f"VERIFY_INDEX_IMPORTS: missing {len(missing)} path(s): {missing}")
    pa = {
        **pa,
        "index_imports_verified": False,
        "status": "needs_index_imports_fix",
        "message": (
            "Страница(ы) импортируют несуществующие файлы: " + ", ".join(missing)
        ),
        "missing_index_imports": missing,
    }
    return {**loop_updates, "project_analysis": pa}


def _route_after_verify_index_imports(state: GenerateAgentState) -> str:
    pa = state.get("project_analysis") or {}
    if pa.get("index_imports_verified"):
        return "end"
    if not (state.get("project_path") or "").strip():
        return "end"
    rounds = int(state.get("_index_import_fix_rounds") or 0)
    if rounds >= MAX_INDEX_IMPORT_FIX_ATTEMPTS:
        print(
            f"VERIFY_INDEX_IMPORTS: лимит попыток правки ({MAX_INDEX_IMPORT_FIX_ATTEMPTS}) → END"
        )
        return "end"
    return "fix_index_imports_llm"
