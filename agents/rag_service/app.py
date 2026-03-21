"""
RAG HTTP-сервис (async): модель и pgvector при старте. Standalone — все зависимости внутри папки.

Запуск из корня репо:
  python -m uvicorn agents.rag_service.app:app --host 0.0.0.0 --port 8000

Запуск только папки rag_service на сервере:
  cd /path/to/rag_service && python -m uvicorn app:app --host 0.0.0.0 --port 8000
  (в папке должны быть app.py, embed.py, pgvector_client.py, .env, requirements.txt)
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# .env в папке rag_service (для standalone-деплоя одной папки)
_SERVICE_DIR = Path(__file__).resolve().parent
if (_SERVICE_DIR / ".env").exists():
    from dotenv import load_dotenv
    load_dotenv(_SERVICE_DIR / ".env")


# --- Модель в памяти (загружается при старте) ---
_embedder = None
_model_name = None


def _get_model():
    global _embedder, _model_name
    if _embedder is None:
        try:
            from .embed import get_embedder, DEFAULT_MODEL
        except ImportError:
            from embed import get_embedder, DEFAULT_MODEL
        _model_name = os.environ.get("RAG_EMBED_MODEL", DEFAULT_MODEL)
        _embedder = get_embedder(_model_name)
    return _embedder


def _get_model_name():
    try:
        from .embed import DEFAULT_MODEL
    except ImportError:
        from embed import DEFAULT_MODEL
    return os.environ.get("RAG_EMBED_MODEL", DEFAULT_MODEL)


def _encode_query_sync(text: str) -> list[float]:
    """Синхронно: один запрос (для поиска), с E5-префиксом при необходимости."""
    try:
        from .embed import E5_QUERY_PREFIX, DEFAULT_MODEL
    except ImportError:
        from embed import E5_QUERY_PREFIX, DEFAULT_MODEL
    model = _get_model()
    name = _get_model_name()
    q = (E5_QUERY_PREFIX + text) if ("e5" in (name or DEFAULT_MODEL).lower()) else text
    arr = model.encode([q], show_progress_bar=False)[0]
    return arr.tolist() if hasattr(arr, "tolist") else list(arr)


def _encode_texts_sync(texts: list[str]) -> list[list[float]]:
    """Синхронно: батч текстов (passage), с E5-префиксом при необходимости."""
    try:
        from .embed import E5_PASSAGE_PREFIX, DEFAULT_MODEL
    except ImportError:
        from embed import E5_PASSAGE_PREFIX, DEFAULT_MODEL
    model = _get_model()
    name = _get_model_name()
    if "e5" in (name or DEFAULT_MODEL).lower():
        texts = [E5_PASSAGE_PREFIX + t for t in texts]
    arr = model.encode(texts, show_progress_bar=len(texts) > 20)
    return arr.tolist() if hasattr(arr, "tolist") else list(arr)


async def _encode_query(text: str) -> list[float]:
    """Асинхронно: encode в пуле потоков, чтобы не блокировать event loop."""
    return await asyncio.to_thread(_encode_query_sync, text)


async def _encode_texts(texts: list[str]) -> list[list[float]]:
    """Асинхронно: батч encode в пуле потоков."""
    return await asyncio.to_thread(_encode_texts_sync, texts)


async def _search_pgvector(query_text: str, top_k: int) -> list[dict]:
    """Async поиск в pgvector: эмбеддинг в потоке, БД через AsyncConnection."""
    import psycopg
    from pgvector import Vector
    from pgvector.psycopg import register_vector_async
    try:
        from .pgvector_client import get_connection_url, RAG_TABLE
    except ImportError:
        from pgvector_client import get_connection_url, RAG_TABLE

    q_embedding = await _encode_query(query_text)
    q_vec = Vector(q_embedding)
    conn_url = get_connection_url()
    async with await psycopg.AsyncConnection.connect(conn_url) as conn:
        await register_vector_async(conn)
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT id, text, file, type, embedding <=> %s AS distance
                FROM {RAG_TABLE}
                ORDER BY embedding <=> %s
                LIMIT %s;
                """,
                (q_vec, q_vec, top_k),
            )
            rows = await cur.fetchall()
    return [
        {
            "text": row[1] or "",
            "file": row[2] or "",
            "type": row[3] or "",
            "distance": float(row[4]) if row[4] is not None else 0.0,
        }
        for row in rows
    ]


# --- Pydantic-модели запросов/ответов ---
class EmbedRequest(BaseModel):
    text: str | None = Field(None, description="Один текст для эмбеддинга")
    texts: list[str] | None = Field(None, description="Несколько текстов (batch)")


class EmbedResponse(BaseModel):
    embedding: list[float] | None = Field(None, description="Один вектор (если передан text)")
    embeddings: list[list[float]] | None = Field(None, description="Список векторов (если передан texts)")


class SearchRequest(BaseModel):
    query: str = Field(..., description="Поисковый запрос")
    top_k: int = Field(5, ge=1, le=100, description="Количество чанков")


class ChunkOut(BaseModel):
    text: str
    file: str
    type: str
    distance: float


class SearchResponse(BaseModel):
    chunks: list[ChunkOut]
    error: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """При старте приложения загружаем модель один раз."""
    _get_model()
    yield
    # shutdown: ничего не чистим


app = FastAPI(
    title="RAG Service",
    description="Эмбеддинги и поиск по pgvector для RAG (модель загружается при старте).",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Проверка, что сервис и модель подняты."""
    try:
        _get_model()
        return {"status": "ok", "model": _get_model_name()}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/embed", response_model=EmbedResponse)
async def embed(body: EmbedRequest):
    """Эмбеддинг одного текста или батча текстов (encode в пуле потоков)."""
    if body.text is not None:
        emb = await _encode_query(body.text)
        return EmbedResponse(embedding=emb, embeddings=None)
    if body.texts is not None and len(body.texts) > 0:
        embs = await _encode_texts(body.texts)
        return EmbedResponse(embedding=None, embeddings=embs)
    raise HTTPException(status_code=400, detail="Укажите text или texts")


@app.post("/search", response_model=SearchResponse)
async def search(body: SearchRequest):
    """Поиск по векторному индексу (pgvector). Async: encode в потоке, БД async."""
    try:
        chunks = await _search_pgvector(body.query, body.top_k)
        return SearchResponse(
            chunks=[ChunkOut(text=c["text"], file=c["file"], type=c["type"], distance=c["distance"]) for c in chunks],
            error=None,
        )
    except Exception as e:
        return SearchResponse(chunks=[], error=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
