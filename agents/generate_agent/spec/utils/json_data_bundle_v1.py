"""
Формат json_data v1 (LangGraph / Studio):

  business:  { "text": str, "files": [ { "url", "fileName", "content" }, ... ] }
  guideline: { "text": str, "files": [...] }
  wishes:    { "text": str, "files": [...] }

Вложения:
- jpg / png / webp / gif / … — только URL попадают в *image_urls (vision в планировании и генерации);
  текстовое описание content для картинок в строки ТЗ не дублируем (только картинки в LLM).
- txt и прочее — content уходит в строки business_requirements / guideline / design_preferences.

После flatten в json_data:
  business_requirements, guideline, design_preferences (строки),
  business_image_urls, guideline_image_urls, wishes_image_urls (списки https URL).
"""
from __future__ import annotations

import copy
from typing import Any
from urllib.parse import urlparse

_IMAGE_EXT = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif", ".svg"}
)


def is_bundle_v1(d: dict[str, Any]) -> bool:
    """True если заданы секции v1 (объекты с text/files), а не только старые строковые поля."""
    if not isinstance(d, dict):
        return False
    if isinstance(d.get("business"), dict):
        return True
    if isinstance(d.get("guideline"), dict):
        return True
    if isinstance(d.get("wishes"), dict):
        return True
    return False


def _file_is_image(file_name: str, url: str) -> bool:
    fn = (file_name or "").lower().strip()
    for ext in _IMAGE_EXT:
        if fn.endswith(ext):
            return True
    try:
        path = urlparse((url or "").strip()).path.lower()
        for ext in _IMAGE_EXT:
            if path.endswith(ext):
                return True
    except Exception:
        pass
    return False


def _format_files_text_only(files: Any) -> str:
    """Только не-изображения: txt и др. — в текст ТЗ."""
    if not isinstance(files, list) or not files:
        return ""
    blocks: list[str] = []
    for i, raw in enumerate(files):
        if not isinstance(raw, dict):
            continue
        url = (raw.get("url") or "").strip()
        fn = (raw.get("fileName") or raw.get("filename") or "").strip()
        content = (raw.get("content") or "").strip()
        if _file_is_image(fn, url):
            continue
        head_parts = [f"--- Вложение {i + 1}"]
        if fn:
            head_parts.append(f"fileName={fn!r}")
        if url:
            head_parts.append(url)
        head = " | ".join(head_parts) + " ---"
        if content:
            blocks.append(f"{head}\n{content}")
        else:
            blocks.append(head)
    return "\n\n".join(blocks).strip()


def _collect_image_urls_https(files: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(files, list):
        return out
    for raw in files:
        if not isinstance(raw, dict):
            continue
        url = (raw.get("url") or "").strip()
        fn = (raw.get("fileName") or raw.get("filename") or "").strip()
        if not _file_is_image(fn, url):
            continue
        if url.startswith("http"):
            out.append(url)
    return out


def _section_to_strings_and_images(
    section: dict[str, Any],
    *,
    title: str,
) -> tuple[str, list[str]]:
    text = (section.get("text") or "").strip()
    files = section.get("files")
    fb = _format_files_text_only(files)
    imgs = _collect_image_urls_https(files)
    parts: list[str] = []
    if text:
        parts.append(text)
    if fb:
        parts.append(f"[{title}: вложения (текст)]\n{fb}")
    return "\n\n".join(parts).strip(), imgs


def flatten_bundle_v1_to_legacy(jd: dict[str, Any]) -> dict[str, Any]:
    """
    Плоский bundle + три списка URL картинок для vision.
    """
    out: dict[str, Any] = {}
    skip = {"business", "guideline", "wishes", "design_preferences"}
    for k, v in jd.items():
        if k in skip:
            continue
        out[k] = copy.deepcopy(v)

    b_imgs: list[str] = []
    g_imgs: list[str] = []
    w_imgs: list[str] = []

    if isinstance(jd.get("business"), dict):
        br, b_imgs = _section_to_strings_and_images(jd["business"], title="Бизнес")
        out["business_requirements"] = br
    elif isinstance(jd.get("business_requirements"), str):
        out["business_requirements"] = jd["business_requirements"]
    else:
        out["business_requirements"] = ""

    if isinstance(jd.get("guideline"), dict):
        gl, g_imgs = _section_to_strings_and_images(jd["guideline"], title="Гайдлайн")
        out["guideline"] = gl
    elif isinstance(jd.get("guideline"), str):
        out["guideline"] = jd["guideline"]
    else:
        out["guideline"] = ""

    wishes = jd.get("wishes") if isinstance(jd.get("wishes"), dict) else {}
    wishes_str, w_imgs = _section_to_strings_and_images(wishes, title="Пожелания")
    dp_existing = jd.get("design_preferences")
    dp_s = dp_existing.strip() if isinstance(dp_existing, str) else ""

    if wishes_str and dp_s:
        out["design_preferences"] = wishes_str + "\n\n" + dp_s
    elif wishes_str:
        out["design_preferences"] = wishes_str
    elif dp_s:
        out["design_preferences"] = dp_s
    else:
        out["design_preferences"] = ""

    if "user_preferences" not in out:
        up = jd.get("user_preferences")
        out["user_preferences"] = copy.deepcopy(up) if isinstance(up, dict) else {}

    out["business_image_urls"] = b_imgs
    out["guideline_image_urls"] = g_imgs
    out["wishes_image_urls"] = w_imgs

    return out


def normalize_json_data(jd: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """
    Если jd — v1, возвращает (legacy, True). Иначе (тот же dict, False).
    """
    if not isinstance(jd, dict):
        return {}, False
    if not is_bundle_v1(jd):
        return jd, False
    return flatten_bundle_v1_to_legacy(jd), True
