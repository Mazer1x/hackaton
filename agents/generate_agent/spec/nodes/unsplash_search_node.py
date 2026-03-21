"""Unsplash search node — fills asset_manifest.images from Unsplash after llm_design_requirements.

HTTP request is made directly in the node (no LangChain tool) so the call always runs
in the same process and .env is loaded here to ensure UNSPLASH_ACCESS_KEY is available.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import httpx

# Ensure .env is loaded when this module runs (e.g. under LangGraph server)
_env_path = Path(__file__).resolve().parents[4] / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=_env_path)
    except Exception:
        pass

log = logging.getLogger(__name__)
_UNSPLASH_URL = "https://api.unsplash.com/search/photos"
_TIMEOUT = 12.0


async def _fetch_unsplash_page(
    query: str,
    orientation: str = "landscape",
    per_page: int = 3,
) -> list[dict[str, Any]]:
    """Call Unsplash API with async client (no blocking in LangGraph event loop)."""
    key = (os.getenv("UNSPLASH_ACCESS_KEY") or "").strip()
    if not key:
        log.warning("Unsplash: UNSPLASH_ACCESS_KEY empty or missing, skipping request")
        return []

    params: dict[str, Any] = {
        "query": query,
        "per_page": min(max(per_page, 1), 10),
        "content_filter": "low",
    }
    if orientation in ("landscape", "portrait", "squarish"):
        params["orientation"] = orientation

    try:
        log.info("Unsplash API GET query=%r orientation=%r", query, orientation)
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _UNSPLASH_URL,
                params=params,
                headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1"},
            )
        log.info("Unsplash API response status=%s", resp.status_code)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.exception("Unsplash API request failed query=%r", query)
        return []

    out: list[dict[str, Any]] = []
    for hit in data.get("results", []):
        urls = hit.get("urls") or {}
        user = hit.get("user") or {}
        name = user.get("name") or user.get("username") or ""
        out.append({
            "id": f"unsplash-{hit.get('id', '')}",
            "source": "unsplash",
            "url": urls.get("regular") or urls.get("raw", ""),
            "url_full": urls.get("full") or urls.get("regular") or urls.get("raw", ""),
            "alt": hit.get("description") or hit.get("alt_description") or query,
            "width": hit.get("width", 0),
            "height": hit.get("height", 0),
            "photographer": name,
            "license": "Unsplash License",
        })
    return out


def _sections_needing_images(layout: dict) -> list[dict]:
    sections = layout.get("sections", [])
    if not sections:
        return []
    out = []
    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        section_id = section.get("id", f"section_{i}")
        raw_elements = section.get("elements", [])
        flat = [json.dumps(e, ensure_ascii=False) if isinstance(e, dict) else str(e) for e in raw_elements]
        has_image_in_elements = any(
            "image" in el.lower() or "photo" in el.lower() or "img" in el.lower()
            for el in flat
        )
        has_image_ratio = bool(section.get("image_ratio"))
        if has_image_in_elements or has_image_ratio:
            out.append({
                "section_id": section_id,
                "role": section.get("role", section_id),
                "image_ratio": section.get("image_ratio"),
            })
    # Fallback: no section had image_ratio/image — treat first N sections as needing an image (hero + 2 more)
    if not out and sections:
        max_fallback = min(3, len(sections))
        for i in range(max_fallback):
            s = sections[i] if isinstance(sections[i], dict) else {}
            out.append({
                "section_id": s.get("id", f"section_{i}"),
                "role": s.get("role", s.get("id", "hero")),
                "image_ratio": s.get("image_ratio", "landscape"),
            })
    return out


async def unsplash_search(state: dict) -> dict:
    """Run Unsplash search per section; build asset_manifest.images (icons stay empty)."""
    layout = state.get("layout_spec") or {}
    brand = state.get("brand_profile") or {}
    image_keywords = brand.get("image_keywords") or []
    sections_list = layout.get("sections") or []
    sections_needing = _sections_needing_images(layout)

    site_target = (state.get("site_target") or "").strip().lower()
    default_ratio = "portrait" if site_target == "mobile" else "landscape"

    # Guarantee at least one request when node runs (so Unsplash dashboard shows activity)
    if not sections_needing:
        sections_needing = [{"section_id": "hero", "role": "hero", "image_ratio": default_ratio}]

    log.info(
        "unsplash_search: layout_spec.sections=%s, sections_needing=%s, image_keywords=%s",
        len(sections_list),
        len(sections_needing),
        (image_keywords or [])[:5],
    )
    if sys.stdout and hasattr(sys.stdout, "flush"):
        try:
            print(f"[unsplash_search] node entered, sections_needing={len(sections_needing)}", flush=True)
        except Exception:
            pass

    images: list[dict[str, Any]] = []
    for i, info in enumerate(sections_needing):
        keyword = image_keywords[i % len(image_keywords)] if image_keywords else info.get("role", info["section_id"])
        ratio_raw = info.get("image_ratio")
        if isinstance(ratio_raw, str) and "portrait" in ratio_raw.lower():
            orientation = "portrait"
        elif isinstance(ratio_raw, str) and "landscape" in ratio_raw.lower():
            orientation = "landscape"
        else:
            orientation = "portrait" if site_target == "mobile" else "landscape"
        results = await _fetch_unsplash_page(keyword, orientation=orientation, per_page=3)
        if not results:
            continue
        hit = results[0]
        images.append({
            "id": hit.get("id", f"unsplash_{info['section_id']}_{i}"),
            "role": info["section_id"],
            "source": "unsplash",
            "url": hit.get("url", ""),
            "url_full": hit.get("url_full", hit.get("url", "")),
            "alt": hit.get("alt", keyword),
            "width": hit.get("width", 1280),
            "height": hit.get("height", 720),
            "photographer": hit.get("photographer", ""),
            "license": hit.get("license", "Unsplash License"),
        })
        log.info("unsplash_search: section %s got image id=%s", i, hit.get("id"))

    log.info("unsplash_search: done, images count=%s", len(images))
    return {"asset_manifest": {"images": images, "icons": []}}
