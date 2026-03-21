# nodes/fix_site_react_node.py
"""
ReAct-нода: вносит правки в код по **запросу пользователя** и/или по сигналам vision (validation_result).
Пайплайн ориентирован на исправление, а не на «валидацию продукта».
"""
from __future__ import annotations

import json
import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agents.validate_agent.state import ValidateAgentState
from agents.validate_agent.llm.tools import get_fix_tools
from agents.validate_agent.llm import get_chat_llm
from agents.validate_agent.nodes.should_fix_or_edit_site import last_human_text

FIX_SITE_SYSTEM = """Ты — инженер фронтенда. Твоя задача — **исправить код** под запрос пользователя или устранить то, что видно на скринах (errors/warnings от vision — это «ещё нужно доделать в коде», не «отчёт аудита»).

Приоритет:
1) **Прямой запрос пользователя** (цвет кнопки, отступы, текст, компонент) — выполни его максимально близко к формулировке.
2) Если передано **vision-резюме** (errors/warnings) — доработай код так, чтобы при следующем деплое скрины отражали желаемый результат.

Инструменты (пути относительно корня проекта):
- read_file_in_project(path)
- write_file_in_project(path, content)
- list_directory_in_project(path)
- shell_execute_in_project(command) — npm run build, npm install и т.д.

Ход работы:
1. Пойми, какие файлы затронуты (страницы Astro, layout, components, *.css).
2. read_file_in_project → правка write_file_in_project → при необходимости build.
3. Не раздувай объём правок: меняй только нужное для запроса.
4. Закончи текстом **только после** успешного write_file_in_project (в ответе инструмента будет строка «File written: …»).

Правила:
- **Запрещено** писать, что правка внесена в репозиторий, пока ты не вызвал write_file_in_project и не получил успешный ответ с «File written:».
- Только относительные пути: "src/pages/index.astro", "src/styles/...".
- Сохраняй стиль проекта (Tailwind/Astro), не ломай разметку без нужды.
- Отвечай кратко; инструменты — основной способ действия."""

MAX_REACT_STEPS = 16
NUDGE_WITHOUT_WRITE_MAX = 3

_WRITE_OK_MARKER = "File written:"


def _had_successful_write(messages: list) -> bool:
    for m in messages:
        if isinstance(m, ToolMessage) and _WRITE_OK_MARKER in str(m.content):
            return True
    return False


def _run_react_loop(project_path: str, validation_result: dict, initial_messages: list) -> list:
    tools = get_fix_tools(project_path)
    model = get_chat_llm(
        model=os.getenv("VALIDATE_FIX_SITE_MODEL") or os.getenv("VALIDATE_FIX_MODEL") or os.getenv("OPENROUTER_MODEL") or "anthropic/claude-sonnet-4",
        temperature=0.3,
        parallel_tool_calls=False,
    )
    llm_with_tools = model.bind_tools(tools, tool_choice="auto")
    current = list(initial_messages)
    nudge_without_write = 0
    for _ in range(MAX_REACT_STEPS):
        response = llm_with_tools.invoke(current)
        if not isinstance(response, AIMessage):
            current.append(response)
            continue
        current.append(response)
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            if _had_successful_write(current):
                break
            if nudge_without_write >= NUDGE_WITHOUT_WRITE_MAX:
                break
            nudge_without_write += 1
            current.append(
                HumanMessage(
                    content=(
                        "Ты ответил без вызова инструментов, но правка в репозитории ещё не зафиксирована "
                        f"(нет успешного ответа с «{_WRITE_OK_MARKER}»). "
                        "Обязательно вызови read_file_in_project при необходимости, затем "
                        "write_file_in_project(path, content) с **полным** содержимым файла. "
                        "Не утверждай, что файл изменён, пока инструмент не вернёт успех."
                    )
                )
            )
            continue
        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("args") or {}
            tool = next((t for t in tools if t.name == name), None)
            if not tool:
                current.append(
                    ToolMessage(
                        content=f"Unknown tool: {name}",
                        tool_call_id=tc.get("id", ""),
                    )
                )
                continue
            try:
                out = tool.invoke(args)
            except Exception as e:
                out = f"Tool error: {e!s}"
            current.append(
                ToolMessage(content=str(out), tool_call_id=tc.get("id", ""))
            )
    return current


def fix_site_react_node(state: ValidateAgentState) -> dict:
    """
    ReAct: правки в коде по validation_result (что ещё не так на скринах) и/или по последнему human-запросу.
    """
    project_path = (state.get("project_path") or "").strip()
    validation_result = state.get("validation_result") or {}
    errors = validation_result.get("errors") or []
    warnings = validation_result.get("warnings") or []
    summary = validation_result.get("summary") or ""

    if not project_path:
        return {"messages": []}

    research = (state.get("edit_research_notes") or "").strip()
    research_block = ""
    if research:
        research_block = (
            f"\n\n**Контекст из веб-поиска (Perplexity, reasoning):**\n{research}\n"
        )

    if errors or warnings:
        user_content = (
            "По скриншотам проверка показала: правка ещё не доведена или есть замечания. **Доработай код**, чтобы визуально выполнить запрос пользователя и убрать указанное ниже.\n\n"
            f"Что ещё нужно исправить (errors):\n{json.dumps(errors, ensure_ascii=False, indent=2)}\n\n"
            f"Замечания (warnings):\n{json.dumps(warnings, ensure_ascii=False, indent=2)}\n\n"
            f"Краткое резюме проверки скринов: {summary}\n\n"
            f"Корень проекта: {project_path}. Только относительные пути (например src/pages/index.astro)."
            f"{research_block}"
        )
    else:
        instr = last_human_text(state)
        if not instr and not research:
            return {"messages": []}
        if instr:
            user_content = (
                "Запрос пользователя (внеси правку в коде; скрины могли ещё не отражать изменение — сделай реализацию в репозитории).\n\n"
                f"Запрос:\n{instr}\n\n"
                f"Корень проекта: {project_path}. Только относительные пути (например src/pages/index.astro)."
                f"{research_block}"
            )
        else:
            user_content = (
                "Внеси правку в коде, опираясь на контекст исследования ниже (прямой текст запроса в чате мог отсутствовать).\n\n"
                f"{research_block}\n"
                f"Корень проекта: {project_path}. Только относительные пути (например src/pages/index.astro)."
            )

    fix_messages = [
        SystemMessage(content=FIX_SITE_SYSTEM),
        HumanMessage(content=user_content),
    ]
    new_messages = _run_react_loop(project_path, validation_result, fix_messages)
    # К state.messages добавляем только новые сообщения (без дублирования system/user)
    appended = new_messages[2:]
    existing = list(state.get("messages") or [])
    return {"messages": existing + appended}
