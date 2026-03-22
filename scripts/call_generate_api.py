"""
Вызов POST /generate и подсказка ожидаемого URL на хостинге (по коду init/deploy).

  py scripts/call_generate_api.py
  py scripts/call_generate_api.py --body deploy/sample_generate_request.json --timeout 7200

URL в ответе: state.deploy_url (если в графе был шаг deploy и hook напечатал DEPLOY_URL:).
Ожидаемый публичный путь до деплоя: https://automatoria.ru/<slug>/ где slug = имя папки project_path.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

_REPO = Path(__file__).resolve().parents[1]


def predicted_automatoria_url(project_path: str | None, repo_name: str | None) -> str:
    slug = "site"
    if project_path:
        slug = Path(project_path.replace("\\", "/")).name or slug
    elif repo_name:
        slug = repo_name.strip("/") or slug
    return f"https://automatoria.ru/{slug}/"


def main() -> None:
    load_dotenv(_REPO / ".env")
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="https://api.progressusbot.ru/generate")
    p.add_argument(
        "--body",
        default=str(_REPO / "deploy" / "sample_generate_request.json"),
        help="JSON файл тела запроса",
    )
    p.add_argument("--timeout", type=float, default=30.0)
    args = p.parse_args()

    body_path = Path(args.body)
    payload = json.loads(body_path.read_text(encoding="utf-8"))
    api_key = (os.environ.get("PROGRESSUSBOT_API_KEY") or "").strip()
    headers = {}
    if api_key:
        headers["X-Progressusbot-Key"] = api_key

    print("Ожидаемый URL сайта (по base из init_project):", predicted_automatoria_url(
        payload.get("project_path"), payload.get("repo_name")
    ))
    print("POST", args.url, flush=True)

    try:
        r = httpx.post(args.url, json=payload, headers=headers, timeout=args.timeout)
        print("HTTP", r.status_code, flush=True)
        try:
            data = r.json()
            print(json.dumps(data, ensure_ascii=False, indent=2)[:8000])
            if isinstance(data, dict) and data.get("ok") and isinstance(data.get("state"), dict):
                du = data["state"].get("deploy_url")
                if du:
                    print("\n>>> deploy_url из ответа:", du)
        except Exception:
            print(r.text[:4000])
    except httpx.TimeoutException:
        print(
            f"Таймаут {args.timeout}s — полная генерация (особенно unified) идёт долго. "
            "Повтори с большим --timeout или смотри логи на сервере.",
            file=sys.stderr,
        )
        sys.exit(124)


if __name__ == "__main__":
    main()
