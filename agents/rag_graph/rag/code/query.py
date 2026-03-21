"""
Запрос к RAG: по тексту запроса возвращает релевантные чанки из PostgreSQL (pgvector).

Запуск из корня проекта:
  python -m agents.rag_graph.rag.code.query "как устроен hero на главной"
  python -m agents.rag_graph.rag.code.query "footer контакты" --top 5

Переменные окружения: RAG_PGVECTOR_URL, RAG_EMBED_MODEL.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from agents.rag_graph.rag.code.embed import embed_query, DEFAULT_MODEL
from agents.rag_graph.rag.code.pgvector_client import get_connection_url, RAG_TABLE


def get_model() -> str:
    return os.environ.get("RAG_EMBED_MODEL", DEFAULT_MODEL)


def query(query_text: str, top_k: int = 5) -> list[dict]:
    """
    Возвращает список релевантных чанков: [{ "text", "file", "type", "distance" }, ...].
    Подключается к БД по RAG_PGVECTOR_URL, ищет по таблице rag_chunks.
    """
    import psycopg
    from pgvector import Vector
    from pgvector.psycopg import register_vector

    try:
        conn_url = get_connection_url()
    except ValueError as e:
        raise FileNotFoundError(
            f"{e}. Задайте RAG_PGVECTOR_URL и выполните: python -m agents.rag_graph.rag.code.build_index"
        ) from e

    q_embedding = embed_query(query_text, get_model())
    # pgvector принимает только Vector или ndarray; list уходит как array и даёт "operator <=> double precision[]"
    q_vec = Vector(q_embedding)

    with psycopg.connect(conn_url) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, text, file, type, embedding <=> %s AS distance
                FROM {RAG_TABLE}
                ORDER BY embedding <=> %s
                LIMIT %s;
                """,
                (q_vec, q_vec, top_k),
            )
            rows = cur.fetchall()

    return [
        {
            "text": row[1] or "",
            "file": row[2] or "",
            "type": row[3] or "",
            "distance": float(row[4]) if row[4] is not None else 0.0,
        }
        for row in rows
    ]


def format_context(chunks: list[dict], max_chars: int = 12000) -> str:
    """Собирает чанки в один текст контекста для вставки в промпт LLM."""
    parts = []
    total = 0
    for c in chunks:
        block = f"--- {c.get('file', '')} ({c.get('type', '')})\n{c.get('text', '')}\n"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="RAG query over Astro code index (pgvector)")
    parser.add_argument("query", nargs="+", help="Поисковый запрос (слова через пробел)")
    parser.add_argument("--top", type=int, default=5, help="Количество чанков (default: 5)")
    parser.add_argument("--context", action="store_true", help="Вывести один блок контекста для LLM")
    args = parser.parse_args()
    q = " ".join(args.query)

    chunks = query(q, top_k=args.top)
    if not chunks:
        print("Ничего не найдено.")
        return

    if args.context:
        print(format_context(chunks))
        return

    for i, c in enumerate(chunks, 1):
        print(f"# {i} [{c.get('distance', 0):.4f}] {c.get('file', '')} | {c.get('type', '')}")
        print("-" * 60)
        text = c.get("text", "")
        if len(text) > 600:
            text = text[:600] + "\n..."
        print(text)
        print()


if __name__ == "__main__":
    main()
