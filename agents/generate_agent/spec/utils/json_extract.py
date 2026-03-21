"""Robust JSON extraction from LLM text responses."""
from __future__ import annotations

import json
import re
from typing import Any


class LLMJsonError(Exception):
    """Raised when the LLM response cannot be parsed as JSON."""


def extract_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from *text*."""
    m = re.search(r"```(?:json)?\s*\n?(\{.*?\})\s*\n?```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    if start < 0:
        raise LLMJsonError("No JSON object found in LLM response")

    depth = 0
    in_string = False
    escape = False
    end = start

    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if depth != 0:
        raise LLMJsonError("Unbalanced braces in LLM JSON response")

    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError as exc:
        raise LLMJsonError(f"Invalid JSON in LLM response: {exc}") from exc
