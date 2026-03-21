# state.py
from typing import Optional

try:
    from typing_extensions import TypedDict
except ImportError:
    from typing import TypedDict


class RAGGraphState(TypedDict):
    """State for RAG search graph."""

    # Input
    query: Optional[str]  # поисковый запрос
    top_k: Optional[int]  # сколько чанков вернуть (default 5)

    # Output (filled by search node)
    chunks: list  # список dict: { "text", "file", "type", "distance" }
    error: Optional[str]  # сообщение об ошибке, если поиск не удался

    # Output (filled by select_best node)
    best_chunk: Optional[dict]  # один чанк, выбранный LLM как самый валидный ответ на query
