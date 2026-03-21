"""
Подключение к PostgreSQL с pgvector для RAG.
Таблица: rag_chunks (id, embedding, text, file, type).
Переменная окружения: RAG_PGVECTOR_URL (postgresql://user:pass@host:port/dbname).
"""
from __future__ import annotations

import os
from pathlib import Path

# Имя таблицы и размерность по умолчанию (MiniLM-L12-v2)
RAG_TABLE = "rag_chunks"
DEFAULT_EMBED_DIM = 384


def _load_dotenv_once() -> None:
    """Загружает .env из корня проекта, чтобы RAG_PGVECTOR_URL подхватывался при CLI-запуске."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    # rag/code -> rag -> rag_graph -> agents -> AutoAi
    root = Path(__file__).resolve().parents[4]
    load_dotenv(root / ".env")


def get_connection_url() -> str:
    _load_dotenv_once()
    url = os.environ.get("RAG_PGVECTOR_URL", "").strip()
    if not url:
        raise ValueError(
            "Задайте RAG_PGVECTOR_URL в .env, например: "
            "postgresql://user:password@31.128.36.124:5432/RAG_data"
        )
    # Таймаут подключения (сек), чтобы не зависать при недоступности сервера
    if "connect_timeout" not in url:
        timeout = os.environ.get("RAG_PGVECTOR_CONNECT_TIMEOUT", "15")
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}connect_timeout={timeout}"
    return url


def get_embed_dim() -> int:
    dim = os.environ.get("RAG_EMBED_DIM", "")
    if dim.isdigit():
        return int(dim)
    return DEFAULT_EMBED_DIM
