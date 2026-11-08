"""Anthropic Claude (Messages API) over httpx - optional, paid. Set ANTHROPIC_API_KEY."""
from __future__ import annotations

import re

import httpx

from fundfacts.config import settings
from fundfacts.llm.base import LLMUnavailable

API_URL = "https://api.anthropic.com/v1/messages"


def generate(system: str, user: str) -> str:
    cfg = settings.llm
    if not cfg.anthropic_api_key:
        raise LLMUnavailable("ANTHROPIC_API_KEY is not set")
    try:
        r = httpx.post(
            API_URL,
            headers={"x-api-key": cfg.anthropic_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={
                "model": cfg.anthropic_model,
                "max_tokens": cfg.max_tokens,
                "temperature": cfg.temperature,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=cfg.timeout_s,
        )
        r.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"{type(exc).__name__}: {str(exc)[:120]}") from exc
    text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    return re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.S).strip()
