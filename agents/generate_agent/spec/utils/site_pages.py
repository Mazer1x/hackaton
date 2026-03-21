"""Normalize multi-page site definition from SessionExport (json_data)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _kebab(s: str) -> str:
    s = s.strip().lower().replace("_", "-")
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


def page_id_to_src_path(page_id: str) -> str:
    """Map logical page id to Astro path. home/index/main → index.astro; else src/pages/<slug>.astro."""
    pid = (page_id or "").strip().lower()
    if pid in ("home", "index", "main", ""):
        return "src/pages/index.astro"
    slug = _kebab(page_id)
    if not slug:
        return "src/pages/index.astro"
    return f"src/pages/{slug}.astro"


def parse_site_pages(raw: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Read site_pages from export. Returns (page_ids ordered, detail dicts for LLM).

    Supported shapes:
    - absent → single-page: (["home"], [detail])
    - ["home", "about", "schedule"] — shorthand
    - [{"id": "home", "title": "...", "path": "/"}, ...] — full
    """
    sp = raw.get("site_pages")
    if not sp:
        return (
            ["home"],
            [{"id": "home", "title": "Главная", "path": "/"}],
        )
    if isinstance(sp, list) and sp and isinstance(sp[0], str):
        ids = [str(x).strip() for x in sp if str(x).strip()]
        if not ids:
            return (["home"], [{"id": "home", "title": "Главная", "path": "/"}])
        details = []
        for i in ids:
            path = "/" if i.lower() in ("home", "index", "main") else f"/{_kebab(i)}"
            details.append({"id": i, "title": i.replace("_", " ").replace("-", " ").title(), "path": path})
        return ids, details

    if isinstance(sp, list) and sp and isinstance(sp[0], dict):
        ids: list[str] = []
        details: list[dict[str, Any]] = []
        for item in sp:
            if not isinstance(item, dict):
                continue
            pid = (item.get("id") or item.get("slug") or "").strip()
            if not pid:
                continue
            ids.append(pid)
            details.append(
                {
                    "id": pid,
                    "title": (item.get("title") or pid).strip(),
                    "path": (item.get("path") or "").strip() or ("/" if pid.lower() in ("home", "index") else f"/{_kebab(pid)}"),
                }
            )
        if not ids:
            return (["home"], [{"id": "home", "title": "Главная", "path": "/"}])
        return ids, details

    return (["home"], [{"id": "home", "title": "Главная", "path": "/"}])


def src_path_to_page_id(rel_path: str, page_ids: list[str]) -> str | None:
    """Map src/pages/*.astro path back to logical page id (inverse of page_id_to_src_path)."""
    if not rel_path or not page_ids:
        return None
    p = rel_path.strip().replace("\\", "/").lstrip("/")
    if not p:
        return None
    norm = "src/pages/" + p if not p.startswith("src/") else p
    for pid in page_ids:
        raw = str(pid).strip()
        if page_id_to_src_path(raw) == norm.replace("\\", "/"):
            return raw
    stem = Path(p).stem.lower()
    for pid in page_ids:
        raw = str(pid).strip()
        if _kebab(raw) == stem or raw.lower() == stem:
            return raw
    return None


def expected_page_paths(page_ids: list[str]) -> list[str]:
    """Ordered Astro paths for canonical page ids (dedupe by path)."""
    seen: set[str] = set()
    out: list[str] = []
    for pid in page_ids:
        p = page_id_to_src_path(pid)
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out
