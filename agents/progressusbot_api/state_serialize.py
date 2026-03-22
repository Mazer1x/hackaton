"""Сериализация state ответа (локальный граф или dict с API)."""
from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage, messages_to_dict


def jsonable_state(state: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in state.items():
        if k == "messages" and v is not None:
            if isinstance(v, list) and v and isinstance(v[0], BaseMessage):
                try:
                    out[k] = messages_to_dict(v)
                except Exception:
                    out[k] = str(v)
            else:
                out[k] = v
        elif isinstance(v, (str, int, float, bool, type(None))):
            out[k] = v
        elif isinstance(v, dict):
            out[k] = v
        elif isinstance(v, list):
            out[k] = list(v)
        else:
            out[k] = str(v)
    return out
