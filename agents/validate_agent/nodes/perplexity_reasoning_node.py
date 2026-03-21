# nodes/perplexity_reasoning_node.py
"""
Reasoning перед правкой кода: LLM + инструмент perplexity_search (актуальные данные из сети).
Результат — edit_research_notes для fix_site_react.
"""
from __future__ import annotations

import json
import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agents.validate_agent.state import ValidateAgentState
from agents.validate_agent.llm import get_chat_llm
from agents.validate_agent.llm.tools.perplexity_tool import get_perplexity_search_tools
from agents.validate_agent.nodes.should_fix_or_edit_site import last_human_text

REASONING_SYSTEM = """Ты — помощник перед правкой фронтенд-кода (Astro, Tailwind, React при необходимости).
Доступен инструмент **perplexity_search** (веб, актуальные факты). Используй его **только когда это правда нужно**.

Когда **не** вызывать perplexity_search (ответь сразу текстом, без инструмента):
- косметика: цвет, шрифт, отступы, текст, картинка, простая вёрстка;
- очевидные правки в уже известных тебе API Tailwind/CSS/Astro;
- задача ясна из запроса и не требует проверки версий или документации.

Когда **стоит** вызвать perplexity_search (один или несколько узких запросов):
- нужны версии пакетов, breaking changes, синтаксис незнакомой библиотеки;
- ошибка сборки/рантайма и нужно свериться с актуальными issue/доками;
- vision перечисляет техническую проблему, для которой нужны факты из сети.

Итог: **краткое резюме на русском** для разработчика. Если поиск не использовал — всё равно дай 2–5 строк, что важно учесть при правке. Если использовал — сожми вывод поиска, без копипасты."""

MAX_REASONING_STEPS = 10


def _reasoning_task_text(state: ValidateAgentState) -> str:
    project_path = (state.get("project_path") or "").strip()
    vr = state.get("validation_result") or {}
    errors = vr.get("errors") or []
    warnings = vr.get("warnings") or []
    summary = vr.get("summary") or ""
    instr = last_human_text(state)
    parts: list[str] = [f"Корень проекта: {project_path}"]
    if instr:
        parts.append(f"Запрос пользователя:\n{instr}")
    if errors or warnings:
        parts.append(
            "По скриншотам / vision (что ещё нужно в коде):\n"
            f"errors:\n{json.dumps(errors, ensure_ascii=False, indent=2)}\n\n"
            f"warnings:\n{json.dumps(warnings, ensure_ascii=False, indent=2)}\n\n"
            f"summary: {summary}"
        )
    if not instr and not (errors or warnings):
        jd = state.get("json_data")
        if isinstance(jd, dict) and jd:
            parts.append(
                "json_data (контекст задачи):\n"
                f"{json.dumps(jd, ensure_ascii=False)[:6000]}"
            )
    return "\n\n".join(parts)


def _run_reasoning_loop(initial_messages: list) -> list:
    tools = get_perplexity_search_tools()
    model_name = (
        os.getenv("VALIDATE_EDIT_REASONING_MODEL")
        or os.getenv("REASONING_MODEL")
        or os.getenv("OPENROUTER_MODEL")
        or "anthropic/claude-haiku-4.5"
    )
    llm = get_chat_llm(
        model=model_name,
        temperature=0.2,
        parallel_tool_calls=False,
    )
    llm_with_tools = llm.bind_tools(tools, tool_choice="auto")
    current = list(initial_messages)
    for _ in range(MAX_REASONING_STEPS):
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
                    ToolMessage(
                        content=f"Неизвестный инструмент: {name}",
                        tool_call_id=tc.get("id", ""),
                    )
                )
                continue
            try:
                out = tool.invoke(args)
            except Exception as e:
                out = f"Ошибка инструмента: {e!s}"
            current.append(
                ToolMessage(content=str(out), tool_call_id=tc.get("id", ""))
            )
    return current


def _final_assistant_text(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            c = m.content
            if c is not None and str(c).strip():
                return str(c).strip()
    return ""


def perplexity_reasoning_node(state: ValidateAgentState) -> dict:
    project_path = (state.get("project_path") or "").strip()
    if not project_path:
        return {}

    if not (os.getenv("OPENROUTER_API_KEY") or "").strip():
        print(
            "perplexity_reasoning: OPENROUTER_API_KEY не задан — пропуск веб-исследования (edit_research_notes пусто)."
        )
        return {"edit_research_notes": ""}

    task = _reasoning_task_text(state)
    # только путь проекта — нечего исследовать
    if task.strip() == f"Корень проекта: {project_path}":
        return {"edit_research_notes": ""}

    initial = [
        SystemMessage(content=REASONING_SYSTEM),
        HumanMessage(
            content=(
                f"{task}\n\n"
                "Оцени задачу: если достаточно общих знаний — сразу дай краткое резюме для правки **без** perplexity_search. "
                "Если нужны свежие факты из интернета — тогда вызови perplexity_search (не чаще необходимого), затем резюме."
            )
        ),
    ]
    trace = _run_reasoning_loop(initial)
    notes = _final_assistant_text(trace)
    return {"edit_research_notes": notes}
