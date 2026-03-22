"""Config for spec pipeline: paths and LLM (OpenRouter)."""
from __future__ import annotations

import os
from pathlib import Path

# Spec package root (agents/generate_agent/spec/)
ROOT_DIR = Path(__file__).resolve().parent
SKILLS_DIR = ROOT_DIR / "skills"
CONTRACTS_DIR = ROOT_DIR / "contracts"
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"
OUTPUT_DIR = ROOT_DIR / "output"
TEMPLATES_DIR = ROOT_DIR / "templates"

# Model tiers for spec pipeline (tools/patterns unchanged; only model id per tier)
# concept tier → page_briefs / guideline inference
MODEL_TIERS: dict[str, str] = {
    "concept": "OPENROUTER_MODEL_CONCEPT",
    "code": "OPENROUTER_MODEL_CODE",
}


def get_env(key: str, default: str | None = None) -> str:
    val = os.getenv(key, default)
    if val is None and default is None:
        raise EnvironmentError(f"Missing required env var: {key}")
    return val or ""


def openrouter_api_key() -> str:
    return get_env("OPENROUTER_API_KEY", "")


def openrouter_base_url() -> str:
    return get_env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")


# Fallback when neither tier nor OPENROUTER_MODEL is set in .env
_DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"



def model_for_tier(tier: str) -> str:
    env_key = MODEL_TIERS.get(tier)
    if env_key is None:
        raise ValueError(f"Unknown model tier: {tier!r}. Use one of {list(MODEL_TIERS)}")
    model = os.getenv(env_key) or os.getenv("OPENROUTER_MODEL", _DEFAULT_MODEL)
    return model
