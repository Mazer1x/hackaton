"""LLM for spec pipeline (OpenRouter)."""
from __future__ import annotations

import logging
from functools import lru_cache

from langchain_openai import ChatOpenAI

from agents.generate_agent.spec.config import (
    model_for_tier,
    openrouter_api_key,
    openrouter_base_url,
)

log = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def get_llm(tier: str, temperature: float = 0.7, max_tokens: int = 8192) -> ChatOpenAI:
    model = model_for_tier(tier)
    log.info("get_llm: tier=%s → model=%s (max_tokens=%d)", tier, model, max_tokens)
    return ChatOpenAI(
        model=model,
        api_key=openrouter_api_key(),
        base_url=openrouter_base_url(),
        temperature=temperature,
        max_tokens=max_tokens,
    )
