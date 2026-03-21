# nodes/screenshot_node.py
"""
Screenshot node: open site in Playwright, scroll the page, take screenshots at each step, save to folder.
Supports file:// (project_path with index.html or dist/index.html) or site_url (http(s)).
Uses async Playwright; only path resolution + mkdir run in a thread to avoid BlockingError.
Для сайтов с защитой: получаем bypass-токен с API, прокидываем в X-Screenshot-Token при запросе fingerprint-key.
"""
import asyncio
import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from agents.validate_agent.state import ValidateAgentState

# API выдачи токена для обхода защиты при скриншотах (если сервис недоступен — работаем без токена)
SCREENSHOT_TOKEN_URL = "http://127.0.0.1:5051/api/screenshot-token"


def get_screenshot_bypass_token() -> Optional[str]:
    """Получить токен перед скриншотом (POST). При ошибке возвращает None — тогда route не вешаем."""
    try:
        import requests
    except ImportError:
        return None
    try:
        resp = requests.post(SCREENSHOT_TOKEN_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return data.get("token") if isinstance(data, dict) else None
    except Exception:
        return None

# Десктоп: широкий вьюпорт для лендингов / десктопной вёрстки
VIEWPORT_WIDTH_DESKTOP = 1920
VIEWPORT_HEIGHT_DESKTOP = 1080
# Мобильный first (site_target / json_data.site_target == mobile)
VIEWPORT_WIDTH_MOBILE = 414
VIEWPORT_HEIGHT_MOBILE = 896
# Задержка после скролла перед скриншотом — минимум для стабильного кадра
SCROLL_TO_SCREENSHOT_DELAY_MS = 180
# Жёсткий лимит на количество скриншотов за один прогон
MAX_SCREENSHOTS = 10
# Даём JS/гидрации время отрисовать контент
INITIAL_LOAD_WAIT_MS = 700
WARMUP_SCROLL_DELAY_MS = 150
# Макс итераций стабилизации высоты (скролл вниз → ждём → пересчитываем height)
MAX_HEIGHT_STABLE_ITERATIONS = 2
STABLE_HEIGHT_WAIT_MS = 350


def _find_index_url(project_path: str) -> Optional[str]:
    root = Path(project_path).resolve()
    if not root.exists():
        return None
    for name in ("index.html", "dist/index.html"):
        p = root / name
        if p.is_file():
            return p.as_uri()
    return None


def _resolve_out_dir_and_url(state: ValidateAgentState) -> tuple[Optional[str], Optional[str], Optional[dict]]:
    """
    Resolve URL and output dir, create dir. Runs in thread. Returns (url, out_dir_str, error_dict).
    Берёт project_path, site_url, screenshot_dir из state или из state["input"] (как в LangGraph Studio).
    """
    inp = state.get("input") if isinstance(state.get("input"), dict) else {}
    project_path = state.get("project_path") or inp.get("project_path") or ""
    site_url = state.get("site_url") or inp.get("site_url")
    screenshot_dir = state.get("screenshot_dir") or inp.get("screenshot_dir")

    if not site_url and not project_path:
        return None, None, {
            "screenshot_paths": [],
            "screenshot_message": "Ошибка: укажите project_path или site_url в Input.",
            "validation_result": {
                "valid": False,
                "errors": ["screenshot_node: need project_path or site_url in state"],
                "warnings": [],
            },
        }

    if site_url:
        url = site_url
        out_dir = Path(screenshot_dir) if screenshot_dir else Path(project_path or ".") / "screenshots"
    else:
        url = _find_index_url(project_path)
        if not url:
            return None, None, {
                "screenshot_paths": [],
                "screenshot_message": f"Ошибка: в папке {project_path} нет index.html или dist/index.html. Соберите сайт: npm run build.",
                "validation_result": {
                    "valid": False,
                    "errors": [f"screenshot_node: no index.html under project_path={project_path}"],
                    "warnings": [],
                },
            }
        out_dir = Path(screenshot_dir) if screenshot_dir else Path(project_path) / "screenshots"

    out_dir = out_dir.resolve()
    os.makedirs(out_dir, exist_ok=True)
    return url, str(out_dir), None


def is_mobile_site_target(state: ValidateAgentState | dict) -> bool:
    """True если в инпуте или json_data задано mobile — скрины с мобильным viewport."""
    st = state.get("site_target")
    if st is None:
        inp = state.get("input")
        if isinstance(inp, dict):
            st = inp.get("site_target")
    if isinstance(st, str) and st.strip().lower() == "mobile":
        return True
    jd = state.get("json_data")
    if isinstance(jd, dict):
        jd_st = jd.get("site_target")
        if isinstance(jd_st, str) and jd_st.strip().lower() == "mobile":
            return True
    return False


def file_prefix_for_page_url(url: str, index: int) -> str:
    """Уникальный префикс файлов скриншотов для страницы (не перезаписывать при многостраничном съёме)."""
    p = urlparse(url)
    parts = [x for x in p.path.strip("/").split("/") if x]
    tail = parts[-1] if parts else "home"
    tail = re.sub(r"[^\w\-]+", "_", tail)[:48]
    return f"p{index:02d}_{tail}"


async def _capture_async(
    url: str,
    out_dir_str: str,
    headless: bool = True,
    *,
    file_prefix: str = "screenshot",
    viewport_width: int = VIEWPORT_WIDTH_DESKTOP,
    viewport_height: int = VIEWPORT_HEIGHT_DESKTOP,
) -> list[str]:
    """Async Playwright: scroll and screenshot. No blocking calls."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return []

    token = await asyncio.to_thread(get_screenshot_bypass_token)

    paths: list[str] = []
    async with async_playwright() as p:
        # При headless=False: slow_mo и снятие дефолтных headless-флагов, чтобы окно точно отображалось
        launch_opts: dict = {"headless": headless}
        if not headless:
            launch_opts["slow_mo"] = 300
            launch_opts["ignore_default_args"] = ["--headless"]
        browser = await p.chromium.launch(**launch_opts)
        try:
            page = await browser.new_page(
                viewport={"width": viewport_width, "height": viewport_height},
            )
            await page.emulate_media(reduced_motion="reduce")

            if token:
                async def add_token(route):
                    await route.continue_(headers={
                        **route.request.headers,
                        "X-Screenshot-Token": token,
                    })

                await page.route("**/api/fingerprint-key", add_token)

            await page.goto(url, wait_until="networkidle" if token else "load", timeout=45000)

            if token:
                try:
                    await page.wait_for_function(
                        "() => document.head.querySelector('style') !== null",
                        timeout=10000,
                    )
                except Exception:
                    # Стиль может не появиться (другая структура страницы или медленная расшифровка) — продолжаем без падения
                    pass

            await page.wait_for_timeout(INITIAL_LOAD_WAIT_MS)

            # Дожидаемся шрифтов, чтобы текст не был пустым/чёрным
            try:
                await page.evaluate("() => (document.fonts && document.fonts.ready) || Promise.resolve()")
                await page.wait_for_timeout(300)
            except Exception:
                pass

            # Сначала прогрев: скролл вниз, чтобы контент успел появиться (opacity 0→1 и ленивая подгрузка).
            # Стили с transition: none НЕ инжектим до прогрева — иначе блоки с opacity:0 так и останутся невидимыми.
            for _ in range(MAX_HEIGHT_STABLE_ITERATIONS):
                prev_height = await page.evaluate("document.documentElement.scrollHeight")
                await page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                await page.wait_for_timeout(WARMUP_SCROLL_DELAY_MS)
                await page.wait_for_timeout(STABLE_HEIGHT_WAIT_MS)
                new_height = await page.evaluate("document.documentElement.scrollHeight")
                if new_height <= prev_height:
                    break

            await page.wait_for_timeout(100)

            # После появления контента: переходы делаем мгновенными (0s), а не отключаем — иначе opacity залипает на 0
            await page.add_style_tag(
                content="* { animation-duration: 0s !important; transition-duration: 0s !important; }"
            )
            await page.wait_for_timeout(50)

            # Возврат наверх и съёмка
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(SCROLL_TO_SCREENSHOT_DELAY_MS)

            step = viewport_height
            n = 0
            y = 0
            seen_max_y = 0
            max_iterations = 500  # защита от бесконечного цикла при растущем контенте
            for _ in range(max_iterations):
                total_height = await page.evaluate("document.documentElement.scrollHeight")
                if total_height <= 0:
                    break
                if y >= total_height:
                    break
                await page.evaluate(f"window.scrollTo(0, {y})")
                await page.wait_for_timeout(SCROLL_TO_SCREENSHOT_DELAY_MS)
                path = Path(out_dir_str) / f"{file_prefix}_{n:04d}.png"
                await page.screenshot(path=str(path))
                paths.append(str(path))
                n += 1
                if n >= MAX_SCREENSHOTS:
                    break
                seen_max_y = y
                y += step
                if n >= MAX_SCREENSHOTS:
                    break
                if y > total_height and seen_max_y < total_height and n < MAX_SCREENSHOTS:
                    # последний кадр — точно в конец
                    await page.evaluate(f"window.scrollTo(0, {total_height})")
                    await page.wait_for_timeout(SCROLL_TO_SCREENSHOT_DELAY_MS)
                    path = Path(out_dir_str) / f"{file_prefix}_{n:04d}.png"
                    await page.screenshot(path=str(path))
                    paths.append(str(path))
                    n += 1
                    if n >= MAX_SCREENSHOTS:
                        break
                if y > total_height:
                    break
        finally:
            await browser.close()

    return paths


async def _screenshot_node(state: ValidateAgentState) -> dict:
    """
    Only blocking part (path resolve + os.makedirs) runs in a thread; Playwright runs async.
    """
    url, out_dir_str, err = await asyncio.to_thread(_resolve_out_dir_and_url, state)
    if err is not None:
        return err

    # headless: из state или input (Studio), допускаем bool или строку "false"/"true"
    raw = state.get("headless")
    if raw is None and isinstance(state.get("input"), dict):
        raw = state.get("input", {}).get("headless")
    if raw is None:
        headless = True
    elif isinstance(raw, bool):
        headless = raw
    else:
        headless = str(raw).lower() not in ("false", "0", "no")

    try:
        mob = is_mobile_site_target(state)
        vw, vh = (
            (VIEWPORT_WIDTH_MOBILE, VIEWPORT_HEIGHT_MOBILE)
            if mob
            else (VIEWPORT_WIDTH_DESKTOP, VIEWPORT_HEIGHT_DESKTOP)
        )
        paths = await _capture_async(
            url,
            out_dir_str,
            headless=headless,
            viewport_width=vw,
            viewport_height=vh,
        )
    except Exception as e:
        return {
            "screenshot_dir": out_dir_str or "",
            "screenshot_paths": [],
            "screenshot_message": f"Ошибка Playwright: {e!s}. Проверьте: при site_url — запущен ли dev-сервер (npm run dev)? При project_path — укажите абсолютный путь.",
            "validation_result": {
                "valid": False,
                "errors": [f"playwright error: {e!s}"],
                "warnings": [],
            },
        }

    msg = f"Сохранено {len(paths)} скриншотов в {out_dir_str}"
    return {
        "screenshot_dir": out_dir_str or "",
        "screenshot_paths": paths,
        "screenshot_message": msg,
    }
