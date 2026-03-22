# nodes/capture_first_screenshots_node.py
"""
Первые скриншоты после init: тот же механизм, что run_screenshots (subprocess run_screenshots.py),
но **разрешён localhost** (GUIDELINE_SITE_URL / site_url), без принудительной подмены на automatoria.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from agents.validate_agent.nodes.screenshot_node import is_mobile_site_target
from agents.validate_agent.utils.page_urls import discover_screenshot_urls

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RUN_SCREENSHOTS_TIMEOUT = 120
DEFAULT_GUIDELINE_SITE_URL = "http://localhost:4321"
DEFAULT_GUIDELINE_LOAD_DELAY = 2


def _get(state: dict, key: str, default=None):
    val = state.get(key)
    if val is not None and val != "":
        return val
    inp = state.get("input")
    if isinstance(inp, dict):
        val = inp.get(key)
        if val is not None and val != "":
            return val
    return default


async def capture_first_screenshots_node(state: dict) -> dict:
    """
    site_url: deploy_url → site_url из state → GUIDELINE_SITE_URL → http://localhost:4321.
    Localhost не отбрасывается (в отличие от run_screenshots_node для validate).
    """
    project_path = (_get(state, "project_path") or "").strip()
    repo_name = _get(state, "repo_name")
    raw_site_url = (
        state.get("deploy_url")
        or _get(state, "site_url")
        or (os.getenv("GUIDELINE_SITE_URL") or "").strip()
        or (DEFAULT_GUIDELINE_SITE_URL if project_path else None)
    )
    site_url = raw_site_url
    screenshot_dir = _get(state, "screenshot_dir")
    headless = True

    if state.get("deploy_url") and site_url:
        delay = int(
            os.getenv("VALIDATE_SITE_LOAD_DELAY_SECONDS", "6") or 6
        )
        if delay > 0:
            await asyncio.sleep(delay)
    elif site_url and "localhost" in site_url:
        delay = int(
            os.getenv("GUIDELINE_SITE_LOAD_DELAY_SECONDS", str(DEFAULT_GUIDELINE_LOAD_DELAY))
            or DEFAULT_GUIDELINE_LOAD_DELAY
        )
        if delay > 0:
            await asyncio.sleep(delay)

    if not site_url and not project_path:
        return {
            "screenshot_paths": [],
            "screenshot_message": "capture_first_screenshots: укажите project_path и/или site_url.",
            "validation_result": {
                "valid": False,
                "errors": ["capture_first_screenshots: need project_path or site_url"],
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

        def _discover() -> list[str]:
            return discover_screenshot_urls(
                site_url,
                project_path=project_path or None,
                json_data=json_data,
                generation_plan=generation_plan,
            )

        page_urls = await asyncio.to_thread(_discover)
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
        returncode, stdout, stderr = await asyncio.to_thread(_run)
    except subprocess.TimeoutExpired:
        return {
            "screenshot_dir": out_dir,
            "screenshot_paths": [],
            "screenshot_message": f"Таймаут run_screenshots ({timeout_sec} с).",
            "validation_result": {
                "valid": False,
                "errors": ["capture_first_screenshots: timeout"],
                "warnings": [],
            },
        }
    except Exception as e:
        return {
            "screenshot_dir": out_dir,
            "screenshot_paths": [],
            "screenshot_message": f"Ошибка: {e!s}",
            "validation_result": {
                "valid": False,
                "errors": [str(e)],
                "warnings": [],
            },
        }

    lines = stdout.strip().split("\n")
    if not lines:
        return {
            "screenshot_dir": out_dir,
            "screenshot_paths": [],
            "screenshot_message": stderr or f"exit {returncode}",
        }
    try:
        data = json.loads(lines[-1])
    except json.JSONDecodeError:
        return {
            "screenshot_dir": out_dir,
            "screenshot_paths": [],
            "screenshot_message": "Невалидный JSON от run_screenshots.",
            "validation_result": {
                "valid": False,
                "errors": [stderr or "bad json"],
                "warnings": [],
            },
        }

    out = {
        "screenshot_dir": data.get("screenshot_dir", out_dir),
        "screenshot_paths": data.get("screenshot_paths", []),
        "screenshot_message": (data.get("screenshot_message") or "")
        + " [capture_first_screenshots]",
    }
    if returncode != 0 and data.get("validation_result"):
        out["validation_result"] = data["validation_result"]
    return out
