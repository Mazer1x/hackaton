"""Unsplash stock photo search tools. Use async fetch for LangGraph (no blocking socket)."""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx
from langchain_core.tools import tool

from agents.generate_agent.spec.config import get_env

log = logging.getLogger(__name__)
_UNSPLASH_URL = "https://api.unsplash.com/search/photos"
_TIMEOUT = 12.0


def _unsplash_key() -> str | None:
    try:
        key = get_env("UNSPLASH_ACCESS_KEY", "")
        return key if key else None
    except EnvironmentError:
        return None


async def fetch_unsplash_page_async(
    query: str,
    orientation: Optional[str] = "landscape",
    per_page: int = 5,
) -> list[dict[str, Any]]:
    """Async Unsplash search; returns list of normalized hit dicts. Use in async nodes (LangGraph)."""
    key = _unsplash_key()
    if not key:
        log.warning("Unsplash API: no key (UNSPLASH_ACCESS_KEY empty or missing)")
        return []

    params: dict[str, Any] = {
        "query": query,
        "per_page": min(max(per_page, 1), 10),
        "content_filter": "low",
    }
    if orientation and orientation in ("landscape", "portrait", "squarish"):
        params["orientation"] = orientation

    results: list[dict[str, Any]] = []
    try:
        log.info("Unsplash API GET (async) query=%r orientation=%r", query, orientation)
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _UNSPLASH_URL,
                params=params,
                headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1"},
            )
        log.info("Unsplash API response status=%s", resp.status_code)
        resp.raise_for_status()
        data = resp.json()
        for hit in data.get("results", []):
            urls = hit.get("urls") or {}
            user = hit.get("user") or {}
            name = user.get("name") or user.get("username") or ""
            results.append({
                "id": f"unsplash-{hit.get('id', '')}",
                "source": "unsplash",
                "url": urls.get("regular") or urls.get("raw", ""),
                "url_full": urls.get("full") or urls.get("regular") or urls.get("raw", ""),
                "alt": hit.get("description") or hit.get("alt_description") or query,
                "width": hit.get("width", 0),
                "height": hit.get("height", 0),
                "photographer": name,
                "license": "Unsplash License",
                "page_url": (hit.get("links") or {}).get("html", ""),
            })
        log.info("Unsplash API query=%r returned %d results", query, len(results))
    except Exception as exc:
        log.exception("Unsplash API request failed query=%r", query)
    return results


@tool
def get_photo_srcset(
    source: str,
    url_full: str,
    widths: Optional[list[int]] = None,
) -> str:
    """Generate responsive srcset URLs for an Unsplash photo."""
    if widths is None:
        widths = [480, 768, 1280, 1920]
    srcset: list[dict] = []
    for w in widths:
        if source == "unsplash" and url_full:
            sep = "&" if "?" in url_full else "?"
            srcset.append({"width": w, "url": f"{url_full}{sep}w={w}&q=80"})
        else:
            srcset.append({"width": w, "url": url_full})
    return json.dumps({"url_full": url_full, "srcset": srcset})


@tool
def search_unsplash_photos(
    query: str,
    orientation: Optional[str] = None,
    per_page: int = 5,
) -> str:
    """Search stock photos on Unsplash. Requires UNSPLASH_ACCESS_KEY in .env. From async nodes use fetch_unsplash_page_async instead."""
    key = _unsplash_key()
    if not key:
        log.warning("Unsplash API: no key (UNSPLASH_ACCESS_KEY empty or missing)")
        return json.dumps({"error": "No Unsplash API key. Set UNSPLASH_ACCESS_KEY in .env"})

    params: dict = {
        "query": query,
        "per_page": min(max(per_page, 1), 10),
        "content_filter": "low",
    }
    if orientation and orientation in ("landscape", "portrait", "squarish"):
        params["orientation"] = orientation

    results_list: list[dict] = []
    try:
        log.info("Unsplash API: search_unsplash_photos (sync) query=%r", query)
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(
                _UNSPLASH_URL,
                params=params,
                headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1"},
            )
        resp.raise_for_status()
        data = resp.json()
        for hit in data.get("results", []):
            urls = hit.get("urls") or {}
            user = hit.get("user") or {}
            name = user.get("name") or user.get("username") or ""
            results_list.append({
                "id": f"unsplash-{hit.get('id', '')}",
                "source": "unsplash",
                "url": urls.get("regular") or urls.get("raw", ""),
                "url_full": urls.get("full") or urls.get("regular") or urls.get("raw", ""),
                "alt": hit.get("description") or hit.get("alt_description") or query,
                "width": hit.get("width", 0),
                "height": hit.get("height", 0),
                "photographer": name,
                "license": "Unsplash License",
                "page_url": (hit.get("links") or {}).get("html", ""),
            })
    except Exception as exc:
        log.exception("Unsplash API: request failed query=%r", query)
        return json.dumps({"query": query, "results": [], "errors": [str(exc)]})
    return json.dumps({"query": query, "results": results_list}, ensure_ascii=False)
