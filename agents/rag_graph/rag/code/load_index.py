"""
Загрузка индекса кода (astro_index_output.json) для RAG.

Формат записей: { "text", "type", "file", "start_byte", "end_byte" }.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

# Корень репо: rag/code -> rag -> rag_graph -> agents -> AutoAi
ROOT = Path(__file__).resolve().parents[4]
# JSON по умолчанию рядом с astro_index.py (в папке rag)
DEFAULT_INDEX_PATH = Path(__file__).resolve().parent.parent / "astro_index_output.json"


def load_chunks(path: Path | str | None = None) -> list[dict[str, Any]]:
    """Загружает JSON-индекс и возвращает список чанков."""
    path = Path(path or DEFAULT_INDEX_PATH)
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        return []
    return [c for c in data if isinstance(c, dict) and "text" in c]


def iter_chunks(path: Path | str | None = None) -> Iterator[dict[str, Any]]:
    """Итератор по чанкам (для потоковой обработки при большом индексе)."""
    for c in load_chunks(path):
        yield c
