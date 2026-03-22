# llm/chat_factory.py
"""
OpenRouter API: https://openrouter.ai — Auth: Bearer OPENROUTER_API_KEY.
Env: OPENROUTER_API_KEY; OPENROUTER_MODEL (fallback). Phase-specific: REASONING_MODEL, LOAD_SKILLS_MODEL, EXECUTE_MODEL; spec: OPENROUTER_MODEL_CONCEPT, OPENROUTER_MODEL_CODE.
"""
import os

from langchain_openai import ChatOpenAI

# Fallback only when OPENROUTER_MODEL is not set in .env
_DEFAULT_MODEL = "openai/gpt-4o-mini"


def get_chat_llm(
    model: str | None = None,
    temperature: float = 0.5,
    max_tokens: int | None = 25000,
    parallel_tool_calls: bool = False,
    reasoning_enabled: bool | None = None,
    **kwargs,
) -> ChatOpenAI:
    """
    Return a LangChain ChatOpenAI-compatible client for OpenRouter.

    reasoning_enabled: ignored for now — OpenAI client rejects unknown kwargs (enable_thinking).
    DeepSeek V3.2 default is non-thinking; other models unaffected.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = model or os.getenv("OPENROUTER_MODEL", _DEFAULT_MODEL)
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
    extra: dict = {"parallel_tool_calls": parallel_tool_calls}
    if max_tokens is not None:
        extra["max_tokens"] = max_tokens
    # Force Vertex AI routing for Google models — avoids "User location is not supported" from Google AI Studio
    if model.startswith("google/"):
        extra["provider"] = {"order": ["Google Vertex"], "allow_fallbacks": False}
    print(f"LLM: OpenRouter {model} (temperature={temperature})")
    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=temperature,
        model_kwargs=extra,
        **kwargs,
    )
