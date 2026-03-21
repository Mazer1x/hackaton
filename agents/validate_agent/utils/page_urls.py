"""
Собирает полные URL страниц для скриншотов валидации (все маршруты под site base).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def normalize_base_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    return u if u.endswith("/") else u + "/"


def join_base_route(base: str, route_segment: str) -> str:
    """route_segment: '' для главной, 'history' для /base/history/ (trailingSlash always)."""
    b = normalize_base_url(base)
    seg = (route_segment or "").strip().strip("/")
    if not seg:
        return b
    return b + seg + "/"


def _route_from_pages_rel(rel: Path) -> str:
    """rel — путь относительно src/pages/, например index.astro, history.astro, blog/post.astro."""
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "index":
        parts = parts[:-1]
    return "/".join(parts)


def discover_urls_from_src_pages(project_path: str, base_url: str) -> list[str]:
    """Сканирует src/pages/**/*.astro и строит URL (пропускает динамические [...] маршруты)."""
    root = Path(project_path).resolve()
    pages = root / "src" / "pages"
    if not pages.is_dir():
        return []
    urls: list[str] = []
    for p in sorted(pages.rglob("*.astro")):
        if any("[" in part for part in p.parts):
            continue
        rel = p.relative_to(pages)
        route = _route_from_pages_rel(rel)
        urls.append(join_base_route(base_url, route))
    return sorted(set(urls))


def _route_from_generation_plan_path(path: str) -> str | None:
    s = path.replace("\\", "/").strip()
    if not s.startswith("src/pages/") or not s.endswith(".astro"):
        return None
    rel = s[len("src/pages/") : -len(".astro")]
    if not rel or rel == "index":
        return ""
    parts = rel.split("/")
    out: list[str] = []
    for i, part in enumerate(parts):
        if "[" in part:
            return None
        if part == "index" and i == len(parts) - 1:
            break
        out.append(part)
    return "/".join(out)


def discover_urls_from_generation_plan(plan: list[str] | None, base_url: str) -> list[str]:
    if not plan:
        return []
    urls: list[str] = []
    for entry in plan:
        if not isinstance(entry, str):
            continue
        r = _route_from_generation_plan_path(entry)
        if r is None:
            continue
        urls.append(join_base_route(base_url, r))
    return sorted(set(urls))


def discover_urls_from_site_pages(site_pages: list[Any] | None, base_url: str) -> list[str]:
    """json_data.site_pages: ['home','history',...] → главная + /history/ и т.д."""
    if not site_pages:
        return []
    out: list[str] = [join_base_route(base_url, "")]
    seen = {out[0]}
    for p in site_pages:
        pid = str(p).strip().lower()
        if not pid or pid in ("home", "index", "main"):
            continue
        u = join_base_route(base_url, pid.replace(" ", "-"))
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def discover_screenshot_urls(
    base_url: str,
    *,
    project_path: str | None = None,
    json_data: dict | None = None,
    generation_plan: list[str] | None = None,
) -> list[str]:
    """
    Полный список URL для проверки. Порядок приоритета:
    1) сканирование src/pages/**/*.astro при наличии project_path;
    2) иначе generation_plan (src/pages/...);
    3) иначе json_data.site_pages;
    4) иначе только главная (base_url).
    """
    base = normalize_base_url(base_url)
    if not base:
        return []

    if project_path:
        from_pages = discover_urls_from_src_pages(project_path, base)
        if from_pages:
            return from_pages

    if generation_plan:
        from_plan = discover_urls_from_generation_plan(generation_plan, base)
        if from_plan:
            return from_plan

    jd = json_data or {}
    sp = jd.get("site_pages")
    if isinstance(sp, list) and sp:
        from_sp = discover_urls_from_site_pages(sp, base)
        if from_sp:
            return from_sp

    return [join_base_route(base, "")]
