"""Google Fonts validation tool."""
from __future__ import annotations

import json
import re
from typing import Optional

import httpx
from langchain_core.tools import tool

_CSS_API = "https://fonts.googleapis.com/css2"
_TIMEOUT = 10.0


def _parse_css_weights(css_text: str) -> list[dict]:
    faces: list[dict] = []
    blocks = re.findall(r"@font-face\s*\{([^}]+)\}", css_text, re.DOTALL)
    for block in blocks:
        style_m = re.search(r"font-style:\s*(\w+)", block)
        weight_m = re.search(r"font-weight:\s*(\d+)", block)
        subset_m = re.search(r"/\*\s*([\w-]+)\s*\*/", block)
        url_m = re.search(r"url\(([^)]+)\)", block)
        if weight_m:
            faces.append({
                "weight": int(weight_m.group(1)),
                "style": style_m.group(1) if style_m else "normal",
                "subset": subset_m.group(1) if subset_m else "latin",
                "url": url_m.group(1) if url_m else None,
            })
    return faces


@tool
def google_fonts_info(family: str, weights: Optional[str] = None) -> str:
    """Validate a Google Font exists and retrieve available weights."""
    if weights:
        weight_list = [w.strip() for w in weights.split(",")]
        weight_spec = ";".join(f"wght@{w}" for w in weight_list)
        ital_spec = ";".join(f"0,{w};1,{w}" for w in weight_list)
    else:
        weight_spec = "wght@100;200;300;400;500;600;700;800;900"
        ital_spec = "0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,100;1,200;1,300;1,400;1,500;1,600;1,700;1,800;1,900"

    result: dict = {"family": family, "available": False}
    with httpx.Client(timeout=_TIMEOUT) as client:
        try:
            resp = client.get(
                _CSS_API,
                params={"family": f"{family}:ital,wght@{ital_spec}"},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code == 200:
                faces = _parse_css_weights(resp.text)
                normal_weights = sorted(set(f["weight"] for f in faces if f["style"] == "normal"))
                italic_weights = sorted(set(f["weight"] for f in faces if f["style"] == "italic"))
                subsets = sorted(set(f["subset"] for f in faces))
                result.update({
                    "available": True,
                    "weights": normal_weights,
                    "italic_weights": italic_weights,
                    "has_italic": len(italic_weights) > 0,
                    "subsets": subsets,
                    "embed_url": f"https://fonts.googleapis.com/css2?family={family.replace(' ', '+')}:ital,wght@{ital_spec}&display=swap",
                })
            elif resp.status_code == 400:
                result["error"] = f"Font '{family}' not found on Google Fonts"
            else:
                result["error"] = f"HTTP {resp.status_code}"
        except Exception as exc:
            result["error"] = str(exc)
    return json.dumps(result, ensure_ascii=False)
