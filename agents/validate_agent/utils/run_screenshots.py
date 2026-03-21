#!/usr/bin/env python3
"""
Локальный запуск или вызов из ноды: снятие скринов по site_url или project_path.
С аргументами (из ноды): --site-url, --screenshot-dir, --headless; без аргументов — дефолты для ручного запуска.
В конце печатает одну строку JSON с screenshot_dir, screenshot_paths, screenshot_message для парсинга нодой.
Скрипт не вызывает граф, а делает resolve + capture сам (чтобы нода могла запускать скрипт без рекурсии).
"""
import argparse
import json
import os
import sys
from pathlib import Path

# utils -> validate_agent -> agents -> repo
ROOT = Path(__file__).resolve().parent.parent.parent.parent


def main():
    import asyncio
    from agents.validate_agent.nodes.screenshot_node import (
        VIEWPORT_HEIGHT_DESKTOP,
        VIEWPORT_HEIGHT_MOBILE,
        VIEWPORT_WIDTH_DESKTOP,
        VIEWPORT_WIDTH_MOBILE,
        _capture_async,
        _resolve_out_dir_and_url,
        file_prefix_for_page_url,
    )

    parser = argparse.ArgumentParser(description="Снять скрины сайта (для ноды или вручную)")
    parser.add_argument("--site-url", default=None, help="URL страницы (например http://localhost:4321)")
    parser.add_argument(
        "--urls-json",
        default=None,
        help="JSON-массив полных URL всех страниц (если задан — снимается каждая страница)",
    )
    parser.add_argument("--screenshot-dir", default=None, help="Папка для скриншотов")
    parser.add_argument("--project-path", default=None, help="Папка с сайтом (index.html или dist/index.html)")
    parser.add_argument("--headless", action="store_true", default=True, help="Не показывать окно браузера (по умолчанию)")
    parser.add_argument("--no-headless", action="store_false", dest="headless", help="Показывать окно браузера")
    parser.add_argument(
        "--mobile",
        action="store_true",
        help="Мобильный viewport 414×896 (иначе десктоп 1920×1080)",
    )
    args = parser.parse_args()

    site_url = args.site_url or "http://localhost:4321"
    screenshot_dir = args.screenshot_dir or str(ROOT / "site1" / "screenshots")
    project_path = args.project_path or ""
    headless = args.headless
    from_node = (
        args.site_url is not None
        or args.urls_json is not None
        or args.screenshot_dir is not None
        or args.project_path is not None
        or args.mobile
    )

    urls_override: list[str] | None = None
    if args.urls_json:
        try:
            parsed = json.loads(args.urls_json)
            if not isinstance(parsed, list):
                raise ValueError("urls-json must be a JSON array")
            urls_override = [str(u).strip() for u in parsed if str(u).strip()]
            if not urls_override:
                urls_override = None
        except Exception as e:
            out = {
                "screenshot_dir": args.screenshot_dir or "",
                "screenshot_paths": [],
                "screenshot_message": f"Ошибка разбора --urls-json: {e!s}",
                "validation_result": {
                    "valid": False,
                    "errors": [f"run_screenshots: invalid urls-json: {e!s}"],
                    "warnings": [],
                },
            }
            print(json.dumps(out), file=sys.stdout, flush=True)
            sys.exit(1)

    if not from_node:
        print("Запуск снятия скринов...")
        print(f"  site_url: {site_url}")
        print(f"  headless: {headless}")
        print("  Сначала запустите в другом терминале:  cd site1 && npm run dev")
        if os.name == "posix" and not os.environ.get("DISPLAY"):
            print("  Внимание: DISPLAY не задан.")
        print()

    if urls_override:
        first = urls_override[0]
        state = {
            "site_url": args.site_url if args.site_url is not None else first,
            "project_path": project_path or "",
            "screenshot_dir": screenshot_dir,
        }
    else:
        state = {
            "site_url": args.site_url if args.site_url is not None else (None if project_path else site_url),
            "project_path": project_path or "",
            "screenshot_dir": screenshot_dir,
        }

    url, out_dir_str, err = _resolve_out_dir_and_url(state)
    if err is not None:
        print(json.dumps(err), file=sys.stdout, flush=True)
        sys.exit(1)

    vw, vh = (
        (VIEWPORT_WIDTH_MOBILE, VIEWPORT_HEIGHT_MOBILE)
        if args.mobile
        else (VIEWPORT_WIDTH_DESKTOP, VIEWPORT_HEIGHT_DESKTOP)
    )

    try:
        async def _run_capture():
            if urls_override:
                acc: list[str] = []
                for i, u in enumerate(urls_override):
                    prefix = file_prefix_for_page_url(u, i)
                    acc.extend(
                        await _capture_async(
                            u,
                            out_dir_str,
                            headless=headless,
                            file_prefix=prefix,
                            viewport_width=vw,
                            viewport_height=vh,
                        )
                    )
                return acc
            return await _capture_async(
                url,
                out_dir_str,
                headless=headless,
                viewport_width=vw,
                viewport_height=vh,
            )

        paths = asyncio.run(_run_capture())
    except Exception as e:
        out = {
            "screenshot_dir": out_dir_str,
            "screenshot_paths": [],
            "screenshot_message": f"Ошибка: {e!s}",
        }
        print(json.dumps(out), file=sys.stdout, flush=True)
        sys.exit(1)

    msg = f"Сохранено {len(paths)} скриншотов в {out_dir_str}"
    out = {
        "screenshot_dir": out_dir_str,
        "screenshot_paths": paths,
        "screenshot_message": msg,
    }
    if not from_node:
        print("Результат:")
        print(f"  {msg}")
        print(f"  Папка: {out_dir_str}")
        if paths:
            print(f"  Файлов: {len(paths)}")
    print(json.dumps(out), file=sys.stdout, flush=True)


if __name__ == "__main__":
    main()
