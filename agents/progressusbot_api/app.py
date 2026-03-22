"""
Публичные маршруты для бота (за reverse proxy): POST /generate, POST /edit.

Режимы (PROGRESSUSBOT_BACKEND):
  local     — ainvoke скомпилированных графов в процессе (по умолчанию).
  langgraph — тот же контракт HTTP, исполнение через LangGraph API (SDK: threads + runs.wait).

Запуск:
  py -m uvicorn agents.progressusbot_api.app:app --host 0.0.0.0 --port 8088

Docker: см. Dockerfile и docker-compose.yml в корне репозитория.
"""
from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from agents.progressusbot_api.langgraph_runner import run_graph
from agents.progressusbot_api.state_serialize import jsonable_state

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")

_BACKEND = os.environ.get("PROGRESSUSBOT_BACKEND", "local").strip().lower() or "local"
if _BACKEND not in ("local", "langgraph"):
    raise RuntimeError(
        f"PROGRESSUSBOT_BACKEND must be 'local' or 'langgraph', got {_BACKEND!r}"
    )

_API_KEY = os.environ.get("PROGRESSUSBOT_API_KEY", "").strip()
_CORS = [
    o.strip()
    for o in os.environ.get("PROGRESSUSBOT_CORS_ORIGINS", "").split(",")
    if o.strip()
]

GRAPH_GENERATE = os.environ.get("PROGRESSUSBOT_GRAPH_GENERATE", "generate_agent").strip()
GRAPH_EDIT = os.environ.get("PROGRESSUSBOT_GRAPH_EDIT", "validate_edit").strip()


def _require_api_key(request: Request) -> None:
    if not _API_KEY:
        return
    header = request.headers.get("x-progressusbot-key") or ""
    auth = request.headers.get("authorization") or ""
    bearer = ""
    if auth.lower().startswith("bearer "):
        bearer = auth[7:].strip()
    candidate = header or bearer
    if not candidate or not secrets.compare_digest(candidate, _API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


class GenerateRequest(BaseModel):
    """Вход для графа generate_agent или unified (см. PROGRESSUSBOT_GRAPH_GENERATE)."""

    prompt: str = Field(..., min_length=1, description="Запрос пользователя (сайт, стиль, контент)")
    project_path: str | None = Field(
        default=None,
        description="Каталог проекта; если не задан — поведение как у агента по умолчанию",
    )
    repo_name: str | None = Field(
        default=None,
        description="Имя репо на git-сервере (sites/{repo}.git); в Docker лучше совпадает с именем папки project_path",
    )
    requirements: dict[str, Any] | None = None
    json_data: dict[str, Any] | None = None
    design_reference_url: str | None = None
    site_target: str | None = Field(default=None, description='"mobile" | "desktop"')


class EditRequest(BaseModel):
    """Вход для графа validate_edit (правки без скриншотов)."""

    task: str = Field(..., min_length=1, description="Что изменить на сайте")
    project_path: str = Field(
        ...,
        min_length=1,
        description="Абсолютный путь к корню репозитория с сайтом",
    )


def _build_generate_initial(body: GenerateRequest) -> dict[str, Any]:
    initial: dict[str, Any] = {
        "messages": [HumanMessage(content=body.prompt)],
        "iteration_count": 0,
        "files_created": [],
    }
    if body.project_path is not None:
        initial["project_path"] = body.project_path
    if body.requirements is not None:
        initial["requirements"] = body.requirements
    if body.json_data is not None:
        initial["json_data"] = body.json_data
    if body.design_reference_url is not None:
        initial["design_reference_url"] = body.design_reference_url
    if body.site_target is not None:
        initial["site_target"] = body.site_target
    if body.repo_name is not None:
        initial["repo_name"] = body.repo_name
    return initial


def _generate_input_for_langgraph(body: GenerateRequest) -> dict[str, Any]:
    """Сообщения в формате, который принимает HTTP API LangGraph."""
    d: dict[str, Any] = {
        "messages": [{"role": "human", "content": body.prompt}],
        "iteration_count": 0,
        "files_created": [],
    }
    if body.project_path is not None:
        d["project_path"] = body.project_path
    if body.requirements is not None:
        d["requirements"] = body.requirements
    if body.json_data is not None:
        d["json_data"] = body.json_data
    if body.design_reference_url is not None:
        d["design_reference_url"] = body.design_reference_url
    if body.site_target is not None:
        d["site_target"] = body.site_target
    if body.repo_name is not None:
        d["repo_name"] = body.repo_name
    return d


def _edit_input_for_langgraph(body: EditRequest) -> dict[str, Any]:
    return {
        "messages": [{"role": "human", "content": body.task}],
        "project_path": body.project_path,
        "screenshot_paths": [],
        "screenshot_urls": [],
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.backend = _BACKEND
    if _BACKEND == "local":
        if GRAPH_GENERATE == "unified":
            from agents.validate_agent.unified_graph import graph as generate_graph
        else:
            from agents.generate_agent.main import graph as generate_graph
        from agents.validate_agent.validate_edit_graph import graph as edit_graph

        app.state.generate_graph = generate_graph
        app.state.edit_graph = edit_graph
    yield


app = FastAPI(
    title="Progressusbot agent API",
    lifespan=lifespan,
    root_path=os.environ.get("PROGRESSUSBOT_ROOT_PATH", "").strip() or "",
)

if _CORS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_CORS,
        allow_credentials=True,
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["*"],
    )


@app.get("/health")
async def health():
    return {"status": "ok", "backend": _BACKEND}


@app.post("/generate", dependencies=[Depends(_require_api_key)])
async def generate(body: GenerateRequest, request: Request):
    """
    Генерация сайта (граф `generate_agent` или GRAPH_GENERATE в env).
    """
    try:
        if request.app.state.backend == "langgraph":
            result = await run_graph(GRAPH_GENERATE, _generate_input_for_langgraph(body))
        else:
            graph = request.app.state.generate_graph
            result = await graph.ainvoke(_build_generate_initial(body))
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "error_type": type(e).__name__},
        )

    return {"ok": True, "state": jsonable_state(result)}


@app.post("/edit", dependencies=[Depends(_require_api_key)])
async def edit(body: EditRequest, request: Request):
    """
    Правки по задаче (граф `validate_edit` или GRAPH_EDIT в env).
    """
    try:
        if request.app.state.backend == "langgraph":
            result = await run_graph(GRAPH_EDIT, _edit_input_for_langgraph(body))
        else:
            graph = request.app.state.edit_graph
            initial: dict[str, Any] = {
                "messages": [HumanMessage(content=body.task)],
                "project_path": body.project_path,
                "screenshot_paths": [],
                "screenshot_urls": [],
            }
            result = await graph.ainvoke(initial)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "error_type": type(e).__name__},
        )

    return {"ok": True, "state": jsonable_state(result)}
