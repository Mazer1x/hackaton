"""
Reference-дизайн: validate _run_screenshots_node → _upload_screenshots_node → удаление локальных PNG
(если upload вернул URL) → vision → design_tokens.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agents.generate_agent.llm.chat_factory import get_chat_llm
from agents.validate_agent.nodes.run_screenshots_node import _run_screenshots_node
from agents.validate_agent.nodes.upload_screenshots_node import _upload_screenshots_node

REPO_ROOT = Path(__file__).resolve().parents[3]
VISION_MODEL_ENV = "VALIDATE_VISION_MODEL"
DEFAULT_VISION_MODEL = "google/gemini-3-flash-preview"
MAX_IMAGES = 8
MAX_IMAGE_BYTES = 1_400_000

DESIGN_TOKENS_SYSTEM = """Ты — дизайн-системный аналитик. По скриншотам **чужого** сайта извлеки визуальный язык
для **нового** проекта (не копируй бренд и тексты — только палитру, настроение, типографику).

Верни **один** JSON-объект без markdown:
{
  "palette": {
    "primary": {"hex": "#RRGGBB"},
    "secondary": {"hex": "#RRGGBB"},
    "accent": {"hex": "#RRGGBB"},
    "background": {"hex": "#RRGGBB"},
    "surface": {"hex": "#RRGGBB"},
    "text": {"hex": "#RRGGBB"}
  },
  "bold_design_move": "одно предложение — главный визуальный приём",
  "motion": {
    "page_transitions": "none | subtle | expressive",
    "micro_interactions": "none | subtle | rich"
  },
  "typography_hint": "кратко про шрифты и плотность текста"
}

Все hex — реалистичные, с экрана."""


def _get(state: dict, key: str, default=None):
    val = state.get(key)
    if val is not None and val != "":
        return val
    inp = state.get("input")
    if isinstance(inp, dict):
        val = inp.get(key)
        if val is not None and val != "":
            return val
    return default


def get_design_reference_url(state: dict) -> str:
    u = (_get(state, "design_reference_url") or "").strip()
    if u:
        return u
    jd = state.get("json_data")
    if isinstance(jd, dict):
        u = (jd.get("design_reference_url") or "").strip()
        if u:
            return u
        prefs = jd.get("user_preferences")
        if isinstance(prefs, dict):
            u = (prefs.get("design_reference_url") or "").strip()
            if u:
                return u
    inp = state.get("input")
    if isinstance(inp, dict):
        inj = inp.get("json_data")
        if isinstance(inj, dict):
            u = (inj.get("design_reference_url") or "").strip()
            if u:
                return u
    return ""


def _explicit_design_forbidden(state: dict) -> bool:
    jd = state.get("json_data")
    if isinstance(jd, dict):
        if jd.get("explicit_design") is True:
            return True
        prefs = jd.get("user_preferences")
        if isinstance(prefs, dict) and prefs.get("explicit_design") is True:
            return True
    return False


def _has_nonempty_palette(state: dict) -> bool:
    t = state.get("design_tokens") or {}
    if not isinstance(t, dict):
        return False
    p = t.get("palette")
    if not isinstance(p, dict) or not p:
        return False
    for v in p.values():
        if isinstance(v, dict) and (v.get("hex") or "").strip():
            return True
        if isinstance(v, str) and v.strip():
            return True
    return False


def should_run_reference_design_pipeline(state: dict) -> bool:
    if _explicit_design_forbidden(state):
        return False
    if _has_nonempty_palette(state):
        return False
    return bool(get_design_reference_url(state))


def _validate_state_for_reference_run(state: dict) -> dict:
    """
    State для _run_screenshots_node: внешний URL в site_url, без project_path — только главная
    (json_data пустой для discover_screenshot_urls).

    Всегда desktop viewport 1920×1080 (см. VIEWPORT_*_DESKTOP в screenshot_node), без --mobile,
    даже если генерируемый сайт mobile-first — референс снимаем как широкий экран.
    """
    ref_url = get_design_reference_url(state)
    project_path = (_get(state, "project_path") or "").strip()
    shot_dir = _get(state, "reference_screenshot_dir")
    if not shot_dir and project_path:
        shot_dir = str(Path(project_path) / "screenshots" / "reference_design")
    if not shot_dir:
        shot_dir = str(REPO_ROOT / "site1" / "screenshots" / "reference_design")

    return {
        "site_url": ref_url,
        "deploy_url": None,
        "repo_name": None,
        "project_path": "",
        "screenshot_dir": shot_dir,
        "json_data": {},
        "generation_plan": None,
        "site_target": "desktop",
        "input": None,
    }


def _parse_json(raw: str) -> dict[str, Any] | None:
    raw = (raw or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if m:
        raw = m.group(1).strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    obj = re.search(r"\{[\s\S]*\}", raw)
    if obj:
        try:
            data = json.loads(obj.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass
    return None


def _image_blocks_from_urls(urls: list[str]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for u in urls[:MAX_IMAGES]:
        if u and isinstance(u, str) and u.startswith("http"):
            blocks.append({"type": "image_url", "image_url": {"url": u}})
    return blocks


def _image_blocks_from_paths(paths: list[str]) -> list[dict[str, Any]]:
    import base64

    blocks: list[dict[str, Any]] = []
    for p in paths[:MAX_IMAGES]:
        try:
            raw = Path(p).read_bytes()
        except Exception:
            continue
        if len(raw) > MAX_IMAGE_BYTES:
            raw = raw[:MAX_IMAGE_BYTES]
        b64 = base64.standard_b64encode(raw).decode("ascii")
        blocks.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
        )
    return blocks


async def run_reference_screenshots_node(state: dict) -> dict:
    """Обёртка над validate _run_screenshots_node."""
    inner = _validate_state_for_reference_run(state)
    out = await _run_screenshots_node(inner)
    return {
        "reference_screenshot_dir": out.get("screenshot_dir"),
        "reference_screenshot_paths": out.get("screenshot_paths") or [],
        "reference_design_message": (out.get("screenshot_message") or "").strip()
        + " [run_reference_screenshots]",
        "validation_result": out.get("validation_result"),
    }


async def upload_reference_screenshots_node(state: dict) -> dict:
    """Обёртка над validate _upload_screenshots_node (screenshot_paths → screenshot_urls)."""
    inner = {
        **state,
        "screenshot_paths": state.get("reference_screenshot_paths") or [],
    }
    out = await _upload_screenshots_node(inner)
    base = (state.get("reference_design_message") or "").strip()
    extra = (out.get("screenshot_message") or "").strip()
    msg = (base + " " + extra).strip() if extra else base
    return {
        "reference_screenshot_urls": out.get("screenshot_urls") or [],
        "reference_design_message": msg + " [upload_reference_screenshots]",
    }


async def delete_reference_screenshots_node(state: dict) -> dict:
    """
    Удаляет локальные PNG после upload, если есть хотя бы один URL (vision пойдёт по ссылкам).
    Если URL не получили — файлы оставляем для fallback base64 в synthesize.
    """
    paths = [p for p in (state.get("reference_screenshot_paths") or []) if p]
    urls = [u for u in (state.get("reference_screenshot_urls") or []) if u and str(u).startswith("http")]
    base_msg = (state.get("reference_design_message") or "").strip()

    if not paths:
        return {"reference_design_message": (base_msg + " [delete_screenshots: nothing to delete]").strip()}

    if not urls:
        return {
            "reference_design_message": (
                base_msg + " [delete_screenshots: skipped — no upload URLs, keeping files for vision fallback]"
            ).strip(),
        }

    removed = 0
    for p in paths:
        try:
            fp = Path(p)
            if fp.is_file():
                fp.unlink()
                removed += 1
        except OSError:
            pass

    extra = f" [delete_screenshots: removed {removed}/{len(paths)} local file(s)]"
    return {
        "reference_screenshot_paths": [],
        "reference_design_message": (base_msg + extra).strip(),
    }


async def synthesize_reference_design_node(state: dict) -> dict:
    http_urls = [u for u in (state.get("reference_screenshot_urls") or []) if u and str(u).startswith("http")]
    paths = [p for p in (state.get("reference_screenshot_paths") or []) if p]

    model = os.getenv(VISION_MODEL_ENV) or os.getenv("OPENROUTER_MODEL") or DEFAULT_VISION_MODEL
    llm = get_chat_llm(model=model, temperature=0.2, max_tokens=4096)
    img_blocks = _image_blocks_from_urls(http_urls) if http_urls else _image_blocks_from_paths(paths)
    if not img_blocks:
        return {
            "reference_design_source": "none",
            "reference_design_error": "Нет URL и нет локальных PNG для vision.",
        }

    ref_url = get_design_reference_url(state)
    via = "по URL (media)" if http_urls else "локально (base64)"
    user_text = (
        f"Reference URL (контекст): {ref_url}\n"
        f"Скриншотов: {len(img_blocks)} ({via}). Извлеки design tokens по системному сообщению."
    )
    user_content: list[str | dict] = [{"type": "text", "text": user_text}]
    user_content.extend(img_blocks)
    messages = [
        SystemMessage(content=DESIGN_TOKENS_SYSTEM),
        HumanMessage(content=user_content),
    ]
    try:
        response = await llm.ainvoke(messages)
        raw = getattr(response, "content", None) or ""
        if isinstance(raw, list):
            parts = []
            for b in raw:
                if isinstance(b, dict) and b.get("type") == "text":
                    parts.append(b.get("text", ""))
                else:
                    parts.append(str(b))
            raw = " ".join(parts)
        raw = str(raw)
        parsed = _parse_json(raw)
        palette = parsed.get("palette") if isinstance(parsed, dict) else None
        if not isinstance(palette, dict) or not palette:
            return {
                "reference_design_source": "failed",
                "reference_design_error": "Модель не вернула palette.",
                "reference_design_raw": raw[:4000],
            }
        tokens: dict[str, Any] = {
            "palette": palette,
            "bold_design_move": (parsed or {}).get("bold_design_move") or "",
            "motion": (parsed or {}).get("motion") if isinstance((parsed or {}).get("motion"), dict) else {},
            "typography_hint": (parsed or {}).get("typography_hint") or "",
            "source": "reference_site_vision",
            "reference_url": ref_url,
        }
        note = f"Design tokens из reference ({len(img_blocks)} скринов, {via})."
        return {
            "design_tokens": tokens,
            "reference_design_source": "vision",
            "reference_design_error": None,
            "site_info": (state.get("site_info") or "").strip() + ("\n" if state.get("site_info") else "") + note,
        }
    except Exception as e:
        return {
            "reference_design_source": "failed",
            "reference_design_error": str(e),
        }
