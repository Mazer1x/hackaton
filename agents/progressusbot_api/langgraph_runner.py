"""Запуск графов через платформенный LangGraph API (threads + runs.wait)."""
from __future__ import annotations

import os
from typing import Any


def _langgraph_base_url() -> str:
    return os.environ.get("LANGGRAPH_API_URL", "http://127.0.0.1:2024").rstrip("/")


def _normalize_wait_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    if isinstance(result, list) and result:
        last = result[-1]
        return last if isinstance(last, dict) else {"values": result}
    return {"result": result}


async def run_graph(graph_id: str, input_state: dict[str, Any]) -> dict[str, Any]:
    from langgraph_sdk import get_client

    client = get_client(url=_langgraph_base_url())
    found = await client.assistants.search(graph_id=graph_id, limit=1)
    if not found:
        raise RuntimeError(
            f"No assistant for graph_id={graph_id!r}. Is LangGraph API running and langgraph.json registered?"
        )
    agent = found[0]
    assistant_id = agent.get("assistant_id") or agent.get("id")
    thread = await client.threads.create()
    raw = await client.runs.wait(
        thread["thread_id"],
        assistant_id,
        input=input_state,
    )
    return _normalize_wait_result(raw)
