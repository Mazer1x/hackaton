# nodes/search_node.py
"""
Нода: поиск по RAG через HTTP API (RAG_SERVICE_URL).
Читает state["query"] и state["top_k"], пишет state["chunks"] и при ошибке state["error"].
"""
from __future__ import annotations

import os

from agents.rag_graph.state import RAGGraphState


def _get(state: RAGGraphState, key: str, default=None):
    """Читает key из state или из state['input'] (LangGraph Studio)."""
    val = state.get(key)
    if val is not None:
        return val
    inp = state.get("input")
    if isinstance(inp, dict):
        return inp.get(key, default)
    # LangGraph Studio иногда шлёт весь ввод строкой в state["input"]
    if key == "query" and isinstance(inp, str) and inp.strip():
        return inp.strip()
    # Чат-формат: последнее сообщение пользователя как query
    if key == "query":
        messages = state.get("messages") or []
        for m in reversed(messages):
            if getattr(m, "type", None) == "human" or type(m).__name__ == "HumanMessage":
                content = getattr(m, "content", "") or ""
                if content and str(content).strip():
                    return str(content).strip()
    return default


def _search_via_service(query_text: str, top_k: int) -> tuple[list, str | None]:
    """Запрос к RAG HTTP-сервису. Возвращает (chunks, error)."""
    import requests
    url = os.environ.get("RAG_SERVICE_URL", "").strip().rstrip("/")
    if not url:
        return [], "Задайте RAG_SERVICE_URL в .env (URL RAG HTTP-сервиса)."
    try:
        r = requests.post(
            f"{url}/search",
            json={"query": query_text, "top_k": top_k},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        chunks = data.get("chunks") or []
        err = data.get("error")
        return list(chunks), err
    except requests.RequestException as e:
        return [], str(e)


def search_node(state: RAGGraphState) -> dict:
    """
    Поиск по RAG через HTTP API (RAG_SERVICE_URL).
    """
    query_text = _get(state, "query") or ""
    top_k = _get(state, "top_k")
    if top_k is None:
        top_k = 5
    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        top_k = 5

    if not (query_text and str(query_text).strip()):
        return {
            "chunks": [],
            "error": "Укажите query в Input (непустой текст запроса).",
        }

    q = str(query_text).strip()
    chunks, err = _search_via_service(q, top_k)
    return {"chunks": chunks, "error": err}
