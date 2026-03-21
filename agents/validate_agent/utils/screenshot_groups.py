"""
Группировка файлов скриншотов по странице: префикс p00_slug_ → одна страница, несколько кадров скролла.
"""
from __future__ import annotations

import re
from pathlib import Path


def page_group_key_from_path(path: str) -> str:
    """
    p00_home_0000.png → p00_home; screenshot_0000.png → screenshot.
    """
    name = Path(path).name
    stem = Path(name).stem
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 4:
        return parts[0]
    return stem


def _page_order_key(group_key: str) -> tuple[int, str]:
    m = re.match(r"^p(\d+)_", group_key)
    if m:
        return (int(m.group(1)), group_key)
    return (10_000, group_key)


def group_screenshot_paths_by_page(paths: list[str]) -> list[tuple[str, list[str]]]:
    """
    Возвращает упорядоченный список (ключ_страницы, пути_кадров).
    Порядок кадров — как в paths; страницы — по индексу p00, p01, ...
    """
    buckets: dict[str, list[str]] = {}
    order: list[str] = []
    for p in paths:
        key = page_group_key_from_path(p)
        if key not in buckets:
            order.append(key)
            buckets[key] = []
        buckets[key].append(p)
    order.sort(key=_page_order_key)
    return [(k, buckets[k]) for k in order]


def page_batches_for_vision(state: dict) -> list[tuple[str, list[str]]]:
    """
    Пары (метка_страницы, список URL кадров) для отдельных vision-запросов.
    Использует screenshot_page_urls после загрузки или восстанавливает порядок из путей + плоского списка URL.
    """
    paths = state.get("screenshot_paths") or []
    urls = state.get("screenshot_urls") or []
    nested = state.get("screenshot_page_urls")
    if nested and isinstance(nested, list) and all(isinstance(x, list) for x in nested):
        groups = group_screenshot_paths_by_page(paths)
        if len(groups) == len(nested):
            return [(groups[i][0], [u for u in nested[i] if u and str(u).startswith("http")]) for i in range(len(nested))]
        return [(f"page_{i+1}", [u for u in batch if u and str(u).startswith("http")]) for i, batch in enumerate(nested)]
    if not urls:
        return []
    if not paths:
        return [("site", [u for u in urls if u and str(u).startswith("http")])]
    groups = group_screenshot_paths_by_page(paths)
    if not groups:
        return [("site", [u for u in urls if u and str(u).startswith("http")])]
    sizes = [len(g[1]) for g in groups]
    if sum(sizes) != len(urls):
        return [("site", [u for u in urls if u and str(u).startswith("http")])]
    i0 = 0
    out: list[tuple[str, list[str]]] = []
    for i, (key, _) in enumerate(groups):
        sz = sizes[i]
        batch = [u for u in urls[i0 : i0 + sz] if u and str(u).startswith("http")]
        out.append((key, batch))
        i0 += sz
    return out
