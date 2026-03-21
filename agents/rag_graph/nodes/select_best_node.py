# nodes/select_best_node.py
"""
Нода: LLM выбирает из state["chunks"] самый релевантный/валидный чанк по state["query"]
и пишет его в state["best_chunk"]. Если чанков нет или ошибка — best_chunk не заполняется.

Модель задаётся переменной окружения RAG_SELECT_LLM_MODEL (OpenRouter, по умолчанию openai/gpt-4o-mini).
"""
from __future__ import annotations

import os
import re

from agents.rag_graph.state import RAGGraphState
from agents.generate_agent.llm.chat_factory import get_chat_llm
from langchain_core.messages import HumanMessage, SystemMessage


def _get(state: RAGGraphState, key: str, default=None):
    val = state.get(key)
    if val is not None:
        return val
    inp = state.get("input")
    if isinstance(inp, dict):
        return inp.get(key, default)
    return default


def _format_candidates(chunks: list[dict], max_text_len: int = 800) -> str:
    lines = []
    for i, c in enumerate(chunks, 1):
        text = (c.get("text") or "")[:max_text_len]
        if len(c.get("text") or "") > max_text_len:
            text += "\n..."
        file_ = c.get("file", "")
        type_ = c.get("type", "")
        lines.append(f"--- Candidate {i} (file: {file_}, type: {type_})\n{text}\n")
    return "\n".join(lines)


def _parse_choice(response_text: str, num_candidates: int) -> int | None:
    """Из текста ответа LLM извлекает номер кандидата (1..num_candidates)."""
    text = (response_text or "").strip()
    # Ищем число в начале строки или после "кандидат", "номер", "number", "1." и т.д.
    for pattern in [
        r"(?:кандидат|номер|number|#|chunk)\s*[:\s]*(\d+)",
        r"^(\d+)\s*[.)\s]",
        r"\b(\d+)\b",
    ]:
        m = re.search(pattern, text, re.I)
        if m:
            n = int(m.group(1))
            if 1 <= n <= num_candidates:
                return n
    # Последняя попытка: любое число в ответе
    nums = re.findall(r"\b(\d+)\b", text)
    for n_str in nums:
        n = int(n_str)
        if 1 <= n <= num_candidates:
            return n
    return None


def select_best_node(state: RAGGraphState) -> dict:
    chunks = state.get("chunks") or []
    error = state.get("error")
    query = _get(state, "query") or ""

    if error or not chunks:
        return {"best_chunk": None}

    if len(chunks) == 1:
        return {"best_chunk": chunks[0]}

    candidates_text = _format_candidates(chunks)
    system = """You choose the most relevant code fragment in response to the user's search query.
You are given a numbered list of candidates (code snippets with file and type). Reply with exactly one number — the candidate number (1, 2, 3, ...) that best matches the query. Do not explain, only the number."""

    user = f"""Query: {query}

Candidates:

{candidates_text}

Number of the best matching candidate (single digit):"""

    try:
        model = os.getenv("RAG_SELECT_LLM_MODEL", "openai/gpt-4o-mini")
        llm = get_chat_llm(model=model, temperature=0.2, max_tokens=50)
        response = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        text = response.content if hasattr(response, "content") else str(response)
        choice = _parse_choice(text, len(chunks))
        if choice is not None:
            return {"best_chunk": chunks[choice - 1]}
        # fallback: первый чанк (минимальная дистанция)
        return {"best_chunk": chunks[0]}
    except Exception as e:
        return {"best_chunk": chunks[0], "error": state.get("error") or f"Select_best: {e!s}"}
