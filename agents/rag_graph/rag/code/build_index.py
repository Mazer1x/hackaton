"""
«Обучение» RAG: загрузка индекса → эмбеддинги → сохранение в PostgreSQL (pgvector).

Запуск из корня проекта:
  python -m agents.rag_graph.rag.code.build_index

Переменные окружения:
  RAG_PGVECTOR_URL  — строка подключения (postgresql://user:pass@host:5432/RAG_data).
  RAG_SOURCE_JSON   — путь к JSON-индексу (по умолчанию agents/rag_graph/rag/astro_index_output.json).
  RAG_EMBED_MODEL   — модель sentence-transformers.
  RAG_EMBED_DIM     — размерность вектора (по умолчанию 384 для MiniLM-L12).
"""
from __future__ import annotations

import os
from pathlib import Path

from agents.rag_graph.rag.code.load_index import load_chunks, DEFAULT_INDEX_PATH, ROOT
from agents.rag_graph.rag.code.embed import embed_texts, DEFAULT_MODEL
from agents.rag_graph.rag.code.pgvector_client import get_connection_url, get_embed_dim, RAG_TABLE


def get_source_json() -> Path:
    return Path(os.environ.get("RAG_SOURCE_JSON", str(DEFAULT_INDEX_PATH)))


def get_model() -> str:
    return os.environ.get("RAG_EMBED_MODEL", DEFAULT_MODEL)


def push_chunks_to_db(chunks: list[dict]) -> None:
    """
    Очищает таблицу rag_chunks, считает эмбеддинги для переданных чанков
    и вставляет их в PostgreSQL (pgvector).
    Чанки: list[dict] с ключами "text", "file", "type", "start_byte" (опц.).
    """
    import psycopg
    from pgvector.psycopg import register_vector

    if not chunks:
        print("Нет чанков для вставки.")
        return

    model_name = get_model()
    embed_dim = get_embed_dim()
    texts = [c["text"] for c in chunks]
    ids = [f"{c.get('file', '')}_{c.get('start_byte', i)}" for i, c in enumerate(chunks)]
    seen = set()
    unique_ids = []
    for i, id_ in enumerate(ids):
        if id_ in seen:
            id_ = f"{id_}_{i}"
        seen.add(id_)
        unique_ids.append(id_)

    print(f"Чанков: {len(chunks)}, модель: {model_name}, размерность: {embed_dim}")
    embeddings = embed_texts(texts, model_name)

    print("Подключение к PostgreSQL...", flush=True)
    conn_url = get_connection_url()
    with psycopg.connect(conn_url) as conn:
        print("Создание расширения и таблицы (если нет)...", flush=True)
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.commit()
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {RAG_TABLE} (
                    id TEXT PRIMARY KEY,
                    embedding vector({embed_dim}),
                    text TEXT NOT NULL,
                    file TEXT NOT NULL DEFAULT '',
                    type TEXT NOT NULL DEFAULT ''
                );
                """
            )
            conn.commit()

            print("Очистка таблицы...", flush=True)
            cur.execute(f"TRUNCATE TABLE {RAG_TABLE};")
            conn.commit()

            print("Вставка чанков...", flush=True)
            batch_size = 100
            for start in range(0, len(unique_ids), batch_size):
                end = min(start + batch_size, len(unique_ids))
                batch_ids = unique_ids[start:end]
                batch_embeddings = embeddings[start:end]
                batch_texts = texts[start:end]
                batch_chunks = chunks[start:end]
                for i in range(len(batch_ids)):
                    cur.execute(
                        f"""
                        INSERT INTO {RAG_TABLE} (id, embedding, text, file, type)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            embedding = EXCLUDED.embedding,
                            text = EXCLUDED.text,
                            file = EXCLUDED.file,
                            type = EXCLUDED.type;
                        """,
                        (
                            batch_ids[i],
                            batch_embeddings[i],
                            batch_texts[i],
                            batch_chunks[i].get("file", ""),
                            batch_chunks[i].get("type", ""),
                        ),
                    )
                conn.commit()
                print(f"  вставлено {end}/{len(unique_ids)}", flush=True)

            print("Создание индекса ivfflat...", flush=True)
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {RAG_TABLE}_embedding_idx
                ON {RAG_TABLE} USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
                """
            )
            conn.commit()

    print("Готово. Векторный индекс в PostgreSQL (таблица rag_chunks).", flush=True)


def build():
    """Загружает чанки из JSON, очищает таблицу и вставляет в PostgreSQL (rag_chunks)."""
    source = get_source_json()
    chunks = load_chunks(source)
    if not chunks:
        raise SystemExit(f"Нет чанков в {source}")
    push_chunks_to_db(chunks)


if __name__ == "__main__":
    build()
