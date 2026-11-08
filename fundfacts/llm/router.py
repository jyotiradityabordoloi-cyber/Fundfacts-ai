"""Pick the configured LLM provider (config `llm.provider`, default auto).

auto -> Gemini if GEMINI_API_KEY is set (free tier), else Claude if ANTHROPIC_API_KEY is set,
        else no LLM: the app answers with exact facts and verified quotes (free, no key needed).
"""
from __future__ import annotations

from fundfacts.config import settings
from fundfacts.llm.base import LLMUnavailable

__all__ = ["LLMUnavailable", "enabled", "provider", "generate"]


def provider() -> str | None:
    return settings.llm.active


def enabled() -> bool:
    return settings.llm.enabled


def generate(system: str, user: str) -> str:
    p = provider()
    if p == "gemini":
        from fundfacts.llm import gemini_client
        return gemini_client.generate(system, user)
    if p == "anthropic":
        from fundfacts.llm import claude_client
        return claude_client.generate(system, user)
    raise LLMUnavailable("no LLM provider configured")
