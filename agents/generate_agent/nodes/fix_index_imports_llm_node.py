# nodes/fix_index_imports_llm_node.py
"""
После verify_index_imports: если импорты в index.astro битые — LLM с контекстом файлов проекта
и инструментами read (весь проект) + write только src/pages/index.astro.
"""
from __future__ import annotations

import os
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from agents.generate_agent.state import GenerateAgentState
from agents.generate_agent.llm.chat_factory import get_chat_llm
from agents.generate_agent.nodes.verify_index_imports_node import (
    MAX_INDEX_IMPORT_FIX_ATTEMPTS,
    _collect_missing_imports,
)

INDEX_REL = "src/pages/index.astro"
SKIP_DIR_NAMES = frozenset(
    {"node_modules", ".git", "dist", ".astro", "__pycache__", ".vercel", ".turbo"}
)
TEXT_SUFFIXES = frozenset({".astro", ".css", ".mjs", ".ts", ".tsx", ".json", ".md"})
MAX_BUNDLE_TOTAL = 140_000
MAX_PER_FILE = 12_000
MAX_FIX_ITERATIONS = 14


def _build_project_bundle(project_root: Path) -> str:
    """Текстовый снимок релевантных файлов (для контекста LLM)."""
    root = project_root.resolve()
    chunks: list[str] = []
    total = 0
    candidates: list[Path] = []
    if root.exists():
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(x in p.parts for x in SKIP_DIR_NAMES):
                continue
            if p.name == "package-lock.json":
                continue
            suf = p.suffix.lower()
            if suf not in TEXT_SUFFIXES and p.name not in (
                "package.json",
                "astro.config.mjs",
                "tsconfig.json",
            ):
                continue
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                continue
            if not rel.startswith("src/") and rel not in (
                "package.json",
                "astro.config.mjs",
                "tsconfig.json",
            ):
                continue
            candidates.append(p)
    candidates.sort(key=lambda x: str(x))
    for p in candidates:
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        body = raw if len(raw) <= MAX_PER_FILE else raw[:MAX_PER_FILE] + "\n... [truncated]\n"
        block = f"\n{'=' * 60}\n# FILE: {p.relative_to(root).as_posix()}\n{'=' * 60}\n{body}\n"
        if total + len(block) > MAX_BUNDLE_TOTAL:
            chunks.append(
                f"\n[... ещё файлы не включены из‑за лимита контекста; используй read_project_file ...]\n"
            )
            break
        chunks.append(block)
        total += len(block)
    return "".join(chunks) if chunks else "(нет текстовых файлов под src/)"


def _make_index_fix_tools(project_path: str) -> list:
    root = Path(project_path).resolve()

    def _resolve(rel: str) -> Path | None:
        rel = rel.strip().lstrip("/").replace("\\", "/")
        p = (root / rel).resolve()
        try:
            p.relative_to(root)
        except ValueError:
            return None
        return p

    @tool
    def read_project_file(path: str) -> str:
        """Прочитать любой файл внутри проекта. Путь от корня проекта, напр. src/components/Hero.astro"""
        p = _resolve(path)
        if p is None:
            return "Доступ запрещён или путь вне проекта."
        if not p.is_file():
            return f"Не файл или не найдено: {path}"
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return f"Ошибка чтения: {e!s}"

    @tool
    def list_src_tree() -> str:
        """Список всех файлов под src/ (пути от корня проекта)."""
        src = root / "src"
        if not src.is_dir():
            return "Нет каталога src/"
        lines = []
        for p in sorted(src.rglob("*")):
            if p.is_file() and not any(x in p.parts for x in SKIP_DIR_NAMES):
                lines.append(p.relative_to(root).as_posix())
        return "\n".join(lines) if lines else "(пусто)"

    @tool
    def write_index_astro(content: str) -> str:
        """
        Записать ТОЛЬКО src/pages/index.astro. Передай полное содержимое файла (frontmatter + разметка).
        Все import из '../...' должны указывать на существующие .astro файлы из списка компонентов/лейаутов.
        """
        target = root / INDEX_REL
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as e:
            return f"Ошибка записи: {e!s}"
        return f"OK: записан {INDEX_REL} ({len(content)} символов)."

    return [read_project_file, list_src_tree, write_index_astro]


FIX_INDEX_SYSTEM = """Ты правишь только главную страницу Astro.

Задача: переписать src/pages/index.astro так, чтобы:
- каждый относительный импорт вида from '../components/X.astro' или from '../layouts/Y.astro' указывал на файл, который РЕАЛЬНО есть в проекте;
- убрать импорты и использование компонентов, для которых нет файла (или создай согласованный минимальный index только из существующих секций);
- сохранить BaseLayout и осмысленный порядок секций, где возможно;
- не трогать другие файлы — у тебя единственная запись: write_index_astro.

Сначала при необходимости вызови list_src_tree или read_project_file. Обязательно вызови write_index_astro с полным исправленным содержимым index.astro."""


def _run_fix_loop(project_path: str, messages: list) -> list:
    tools = _make_index_fix_tools(project_path)
    model = get_chat_llm(
        model=os.getenv("FIX_INDEX_MODEL")
        or os.getenv("EXECUTE_MODEL")
        or os.getenv("OPENROUTER_MODEL"),
        temperature=0.25,
        parallel_tool_calls=False,
    )
    llm_with_tools = model.bind_tools(tools, tool_choice="auto")
    current = list(messages)
    for _ in range(MAX_FIX_ITERATIONS):
        response = llm_with_tools.invoke(current)
        if not isinstance(response, AIMessage):
            current.append(response)
            continue
        current.append(response)
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            break
        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("args") or {}
            tool = next((t for t in tools if t.name == name), None)
            if not tool:
                current.append(
                    ToolMessage(content=f"Unknown tool: {name}", tool_call_id=tc.get("id", ""))
                )
                continue
            try:
                out = tool.invoke(args)
            except Exception as e:
                out = f"Tool error: {e!s}"
            current.append(ToolMessage(content=str(out), tool_call_id=tc.get("id", "")))
    return current


def _fix_index_imports_llm_node(state: GenerateAgentState) -> dict:
    pa = dict(state.get("project_analysis") or {})
    project_path = (state.get("project_path") or "").strip()
    if not project_path:
        return {
            "_verify_after_fix": True,
            "_index_import_fix_rounds": MAX_INDEX_IMPORT_FIX_ATTEMPTS,
        }

    root = Path(project_path)
    missing = pa.get("missing_index_imports") or _collect_missing_imports(
        root / "src" / "pages" / "index.astro", root
    )
    bundle = _build_project_bundle(root)

    user = f"""PROJECT_PATH: {project_path}

Проблема: в index.astro есть импорты на несуществующие файлы (или нет index):
Missing paths (ожидаемые цели): {missing}

Ниже снимок файлов проекта (src + корневые конфиги). При необходимости дочитай через read_project_file.

{bundle}

Вызови write_index_astro с полным исправленным содержимым src/pages/index.astro."""

    msgs = [
        SystemMessage(content=FIX_INDEX_SYSTEM),
        HumanMessage(content=user),
    ]
    new_msgs = _run_fix_loop(project_path, msgs)
    appended = new_msgs[2:]

    # Перепроверка после LLM
    missing_after = _collect_missing_imports(root / "src" / "pages" / "index.astro", root)
    if not missing_after:
        pa = {
            **pa,
            "index_imports_verified": True,
            "missing_index_imports": [],
            "status": "complete",
            "message": (pa.get("message") or "") + " | index.astro исправлен (LLM), импорты OK.",
        }
        print("FIX_INDEX_IMPORTS_LLM: после правки — импорты OK.")
    else:
        pa = {
            **pa,
            "index_imports_verified": False,
            "status": "needs_index_imports_fix",
            "missing_index_imports": missing_after,
            "message": f"После LLM всё ещё битые импорты: {', '.join(missing_after)}",
        }
        print(f"FIX_INDEX_IMPORTS_LLM: после правки всё ещё missing: {missing_after}")

    out: dict = {
        "project_analysis": pa,
        "_verify_after_fix": True,
        "_index_import_fix_rounds": int(state.get("_index_import_fix_rounds") or 0) + 1,
    }
    if appended:
        out["messages"] = appended
    return out
