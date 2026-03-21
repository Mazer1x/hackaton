"""Validate spec artifacts against JSON Schema in spec/contracts."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator, ValidationError

from agents.generate_agent.spec.config import CONTRACTS_DIR

_cache: dict[str, Draft7Validator] = {}


def _get_validator(schema_name: str) -> Draft7Validator:
    if schema_name not in _cache:
        if not schema_name.endswith(".json"):
            schema_name += ".json"
        path = CONTRACTS_DIR / schema_name
        if not path.exists():
            raise FileNotFoundError(f"Schema not found: {path}")
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft7Validator.check_schema(schema)
        _cache[schema_name] = Draft7Validator(schema)
    return _cache[schema_name]


def validate(data: dict, schema_name: str) -> list[str]:
    """Returns list of error messages (empty if valid)."""
    try:
        v = _get_validator(schema_name)
    except FileNotFoundError:
        return []
    errors: list[str] = []
    for err in sorted(v.iter_errors(data), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(p) for p in err.absolute_path) or "(root)"
        errors.append(f"{path}: {err.message}")
    return errors
