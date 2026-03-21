"""Normalize site_target from input JSON: mobile vs desktop (default desktop)."""
from __future__ import annotations

from typing import Any, Literal

SiteTarget = Literal["mobile", "desktop"]


def normalize_site_target(value: Any) -> SiteTarget:
    """Return 'mobile' or 'desktop'. Only those two strings are accepted; anything else → 'desktop'."""
    if value is None:
        return "desktop"
    s = str(value).strip().lower()
    if s == "mobile":
        return "mobile"
    if s == "desktop":
        return "desktop"
    return "desktop"
