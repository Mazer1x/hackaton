# state.py
from typing import Annotated, Optional

try:
    from typing_extensions import TypedDict
except ImportError:
    from typing import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from agents.generate_agent.state import _merge_project_path


class ValidateAgentState(TypedDict):
    """State for validation agent. Те же поля ТЗ/spec, что у generate_agent — для теста тем же входным JSON."""
    messages: Annotated[list[BaseMessage], add_messages]

    # Input to validate (e.g. project path, spec, json_data) — тот же reducer, что в GenerateAgentState (deploy_git)
    project_path: Annotated[Optional[str], _merge_project_path]  # папка с сайтом (ищем index.html или dist/index.html) — лучше абсолютный путь
    site_url: Optional[str]  # адрес сайта: http://localhost:4321 или https://... (приоритет над project_path)
    site_target: Optional[str]  # "mobile" | "desktop" — при mobile скрины 414×896
    headless: Optional[bool]  # false = показывать браузер при скриншотах (по умолчанию true)
    json_data: Optional[dict]
    project_spec: Optional[dict]
    generation_plan: Optional[list[str]]  # как в generate_agent — для маршрутов при отсутствии src/pages на диске

    # ТЗ / spec pipeline (тот же вид, что в generate_agent — чтобы гнать validate тем же входным JSON)
    requirements: Optional[dict]
    design_tokens: Optional[dict]
    session_export: Optional[dict]
    site_architecture: Optional[dict]
    site_info: Optional[str]
    canonical_spec: Optional[dict]
    brand_profile: Optional[dict]
    typography_spec: Optional[dict]
    layout_spec: Optional[dict]
    background_spec: Optional[dict]
    asset_manifest: Optional[dict]
    animation_spec: Optional[dict]

    # Validation result
    validation_result: Optional[dict]
    # e.g. {"valid": bool, "errors": [...], "warnings": [...]}

    # validate_edit: perplexity_reasoning → краткие выводы для fix_site_react
    edit_research_notes: Optional[str]

    # Screenshots (filled by screenshot node)
    screenshot_dir: Optional[str]
    screenshot_paths: list[str]
    screenshot_message: Optional[str]  # краткое сообщение для UI: "Сохранено N скринов в ..." или текст ошибки
    screenshot_urls: list[str]  # URL после загрузки на сервер (https://media.automatoria.ru/screenshots/...)
    screenshot_page_urls: Optional[list[list[str]]]  # URL по страницам (после upload); для N отдельных анализов

    # Deploy (filled by deploy_git node at start)
    repo_name: Optional[str]  # имя репозитория на git-сервере (sites/{repo_name}.git)
    deploy_log: Optional[str]  # лог git init/add/commit/push
    deploy_url: Optional[str]  # DEPLOY_URL из post-receive hook (https://automatoria.ru/...)

    # Fix loop: after deploy failure, fix_deploy runs once then we retry deploy
    fix_attempts: Optional[int]  # 0 = not yet fixed; 1 = already ran fix_deploy once

    # RAG index (optional / legacy; index_code_to_rag node removed)
    rag_indexed: Optional[bool]
    rag_chunks_count: Optional[int]
    rag_message: Optional[str]
