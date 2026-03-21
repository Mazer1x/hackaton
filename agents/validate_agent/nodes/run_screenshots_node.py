# nodes/run_screenshots_node.py
"""
Нода: запускает agents.validate_agent.utils.run_screenshots в отдельном процессе.
Скрины снимаются так же, как при локальном запуске скрипта (в т.ч. из UI).
"""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from agents.validate_agent.state import ValidateAgentState
from agents.validate_agent.nodes.screenshot_node import is_mobile_site_target
from agents.validate_agent.utils.page_urls import discover_screenshot_urls

# Корень репо (nodes -> validate_agent -> agents -> repo)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RUN_SCREENSHOTS_TIMEOUT = 120
# Задержка (сек) перед снятием скринов после деплоя, чтобы сайт успел подняться. VALIDATE_SITE_LOAD_DELAY_SECONDS в .env
DEFAULT_SITE_LOAD_DELAY = 6


def _get(state: ValidateAgentState, key: str, default=None):
    """Читает key из state или из state['input'] (как приходит из LangGraph Studio)."""
    val = state.get(key)
    if val is not None and val != "":
        return val
    inp = state.get("input")
    if isinstance(inp, dict):
        val = inp.get(key)
        if val is not None and val != "":
            return val
    return default


async def _run_screenshots_node(state: ValidateAgentState) -> dict:
    """
    Запускает run_screenshots.py в subprocess с аргументами из state.
    Скрипт в конце печатает одну строку JSON — парсим последнюю строку stdout.
    site_url: никогда не используем localhost — только deploy_url или https://automatoria.ru/{repo_name}/
    """
    repo_name = _get(state, "repo_name") or state.get("repo_name")
    # Приоритет: deploy_url (только что задеплоенный сайт) → site_url из инпута → URL по repo_name.
    # Иначе после деплоя в другой repo скрины снимались бы со старого site_url из Input.
    raw_site_url = state.get("deploy_url") or _get(state, "site_url")
    if raw_site_url and "localhost" in raw_site_url:
        raw_site_url = None
    site_url = raw_site_url or (f"https://automatoria.ru/{repo_name}/" if repo_name else None)
    project_path = _get(state, "project_path") or ""
    screenshot_dir = _get(state, "screenshot_dir")
    # Всегда headless при запуске из ноды (Studio/API без DISPLAY)
    headless = True

    # После деплоя даём время сайту подняться перед снятием скринов
    if state.get("deploy_url") and site_url:
        delay_sec = int(os.getenv("VALIDATE_SITE_LOAD_DELAY_SECONDS", str(DEFAULT_SITE_LOAD_DELAY)) or DEFAULT_SITE_LOAD_DELAY)
        if delay_sec > 0:
            await asyncio.sleep(delay_sec)

    if not site_url and not project_path:
        return {
            "screenshot_paths": [],
            "screenshot_message": "Ошибка: укажите project_path или site_url в Input.",
            "validation_result": {
                "valid": False,
                "errors": ["run_screenshots_node: need project_path or site_url in state"],
                "warnings": [],
            },
        }

    out_dir = screenshot_dir
    if not out_dir and project_path:
        out_dir = str(Path(project_path) / "screenshots")
    if not out_dir:
        out_dir = str(REPO_ROOT / "site1" / "screenshots")

    cmd = [
        sys.executable,
        "-m",
        "agents.validate_agent.utils.run_screenshots",
        "--screenshot-dir",
        out_dir,
        "--headless" if headless else "--no-headless",
    ]
    page_urls: list[str] = []
    if site_url:
        cmd.extend(["--site-url", site_url])
        jd = _get(state, "json_data")
        json_data = jd if isinstance(jd, dict) else None
        gp = _get(state, "generation_plan")
        generation_plan = gp if isinstance(gp, list) else None
        # В LangGraph dev async-ноде блокирует event loop (scandir/rglob). Выполняем в пуле потоков.
        def _discover_page_urls() -> list[str]:
            return discover_screenshot_urls(
                site_url,
                project_path=project_path or None,
                json_data=json_data,
                generation_plan=generation_plan,
            )

        page_urls = await asyncio.to_thread(_discover_page_urls)
        if page_urls:
            cmd.extend(["--urls-json", json.dumps(page_urls)])
    elif project_path:
        cmd.extend(["--project-path", project_path])

    if is_mobile_site_target(state):
        cmd.append("--mobile")

    n_pages = max(1, len(page_urls)) if site_url else 1
    timeout_sec = min(max(RUN_SCREENSHOTS_TIMEOUT, 40 * n_pages), 900)

    def _run() -> tuple[int, str, str]:
        r = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env={**os.environ},
        )
        return r.returncode, r.stdout or "", r.stderr or ""

    try:
        returncode, stdout, stderr = await asyncio.to_thread(
            _run,
        )
    except subprocess.TimeoutExpired:
        return {
            "screenshot_dir": out_dir,
            "screenshot_paths": [],
            "screenshot_message": f"Таймаут запуска скрипта ({timeout_sec} с).",
            "validation_result": {
                "valid": False,
                "errors": ["run_screenshots: timeout"],
                "warnings": [],
            },
        }
    except Exception as e:
        return {
            "screenshot_dir": out_dir,
            "screenshot_paths": [],
            "screenshot_message": f"Ошибка запуска скрипта: {e!s}",
            "validation_result": {
                "valid": False,
                "errors": [str(e)],
                "warnings": [],
            },
        }

    lines = stdout.strip().split("\n")
    if not lines:
        if returncode != 0:
            return {
                "screenshot_dir": out_dir,
                "screenshot_paths": [],
                "screenshot_message": stderr or f"Скрипт завершился с кодом {returncode}",
                "validation_result": {
                    "valid": False,
                    "errors": [stderr or f"exit code {returncode}"],
                    "warnings": [],
                },
            }
        return {
            "screenshot_dir": out_dir,
            "screenshot_paths": [],
            "screenshot_message": "Скрипт не вернул результат (пустой stdout).",
        }
    try:
        data = json.loads(lines[-1])
    except json.JSONDecodeError:
        if returncode != 0:
            return {
                "screenshot_dir": out_dir,
                "screenshot_paths": [],
                "screenshot_message": stderr or f"Скрипт завершился с кодом {returncode}",
                "validation_result": {
                    "valid": False,
                    "errors": [stderr or f"exit code {returncode}"],
                    "warnings": [],
                },
            }
        return {
            "screenshot_dir": out_dir,
            "screenshot_paths": [],
            "screenshot_message": "Скрипт не вернул валидный JSON.",
        }
    out = {
        "screenshot_dir": data.get("screenshot_dir", out_dir),
        "screenshot_paths": data.get("screenshot_paths", []),
        "screenshot_message": data.get("screenshot_message", ""),
    }
    if returncode != 0 and data.get("validation_result"):
        out["validation_result"] = data["validation_result"]
    elif returncode != 0:
        out["validation_result"] = {
            "valid": False,
            "errors": [data.get("screenshot_message", stderr or f"exit code {returncode}")],
            "warnings": [],
        }
    return out
