"""Case-insensitive file existence under project root (Linux: Hero.astro matches hero.astro)."""
from __future__ import annotations

from pathlib import Path


def _norm_rel(rel: str) -> str:
    return rel.strip().replace("\\", "/").lstrip("/")


def resolve_project_file(project_root: Path, rel: str) -> Path | None:
    """
    If a file exists under project_root at rel, return the actual path (exact match first,
    then same path with different letter case). Otherwise None.
    """
    rel = _norm_rel(rel)
    if not rel:
        return None
    root = project_root.resolve()
    parts = [p for p in rel.split("/") if p and p != "."]
    if ".." in parts:
        return None
    if not parts:
        return None
    cur: Path = root
    for i, part in enumerate(parts):
        is_last = i == len(parts) - 1
        exact = cur / part
        if exact.exists():
            if is_last:
                return exact if exact.is_file() else None
            if not exact.is_dir():
                return None
            cur = exact
            continue
        if not cur.is_dir():
            return None
        match: Path | None = None
        try:
            for child in cur.iterdir():
                if child.name.lower() == part.lower():
                    match = child
                    break
        except OSError:
            return None
        if match is None:
            return None
        if is_last:
            return match if match.is_file() else None
        if not match.is_dir():
            return None
        cur = match
    return None


def file_exists_case_insensitive(project_root: Path, rel: str) -> bool:
    return resolve_project_file(project_root, rel) is not None
