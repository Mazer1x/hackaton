"""
Эмбеддинги для RAG HTTP-сервиса (standalone-деплой).
"""
from __future__ import annotations

from typing import List

# Модель по умолчанию (мультиязычная, хорошо на CPU)
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Для E5 при retrieval рекомендуют префиксы (см. карточку модели на Hugging Face)
E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "


def get_embedder(model_name: str | None = None):
    """Ленивая загрузка SentenceTransformer."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(model_name or DEFAULT_MODEL)


def _is_e5(model_name: str) -> bool:
    return "e5" in (model_name or DEFAULT_MODEL).lower()


def embed_texts(texts: List[str], model_name: str | None = None) -> List[List[float]]:
    """Считает эмбеддинги для списка строк. Возвращает list of vectors."""
    name = model_name or DEFAULT_MODEL
    model = get_embedder(model_name)
    if _is_e5(name):
        texts = [E5_PASSAGE_PREFIX + t for t in texts]
    arr = model.encode(texts, show_progress_bar=len(texts) > 20)
    return arr.tolist() if hasattr(arr, "tolist") else list(arr)


def embed_query(query: str, model_name: str | None = None) -> List[float]:
    """Эмбеддинг одного запроса (для поиска)."""
    name = model_name or DEFAULT_MODEL
    model = get_embedder(model_name)
    q = (E5_QUERY_PREFIX + query) if _is_e5(name) else query
    arr = model.encode([q], show_progress_bar=False)[0]
    return arr.tolist() if hasattr(arr, "tolist") else list(arr)
