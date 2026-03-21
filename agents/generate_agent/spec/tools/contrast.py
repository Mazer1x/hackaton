"""WCAG contrast ratio checking tool."""
from __future__ import annotations

import json
from langchain_core.tools import tool


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _relative_luminance(r: int, g: int, b: int) -> float:
    def linearize(v: int) -> float:
        s = v / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def _contrast_ratio(lum1: float, lum2: float) -> float:
    return (max(lum1, lum2) + 0.05) / (min(lum1, lum2) + 0.05)


@tool
def check_contrast_ratio(foreground: str, background: str) -> str:
    """Check WCAG contrast ratio between two hex colors (e.g. #1a1a1a and #fafafa)."""
    try:
        fg_rgb = _hex_to_rgb(foreground)
        bg_rgb = _hex_to_rgb(background)
    except (ValueError, IndexError):
        return json.dumps({"error": "Invalid hex colors"})
    ratio = _contrast_ratio(_relative_luminance(*fg_rgb), _relative_luminance(*bg_rgb))
    return json.dumps({
        "foreground": foreground,
        "background": background,
        "ratio": round(ratio, 2),
        "aa_normal": ratio >= 4.5,
        "aa_large": ratio >= 3.0,
    })
