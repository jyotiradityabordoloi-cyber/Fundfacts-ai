"""Google Gemini (Generative Language API) over httpx.

Free tier: create a key at https://aistudio.google.com/app/apikey (no credit card) and set
GEMINI_API_KEY. Note: on Google's free tier, prompts may be used by Google to improve its
products - FundFacts AI only ever sends the question (after the PII guardrail) and public
document passages.
"""
from __future__ import annotations

import httpx

from fundfacts.config import settings
from fundfacts.llm.base import LLMUnavailable

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def generate(system: str, user: str) -> str:
    cfg = settings.llm
    if not cfg.gemini_api_key:
        raise LLMUnavailable("GEMINI_API_KEY is not set")
    gen = {"temperature": cfg.temperature, "maxOutputTokens": cfg.max_tokens, "responseMimeType": "application/json"}
    if "2.5" in cfg.gemini_model:
        gen["thinkingConfig"] = {"thinkingBudget": 0}  # short factual answers: no hidden reasoning tokens
    try:
        r = httpx.post(
            API_URL.format(model=cfg.gemini_model),
            headers={"x-goog-api-key": cfg.gemini_api_key, "content-type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": gen,
            },
            timeout=cfg.timeout_s,
        )
        r.raise_for_status()
    except httpx.HTTPError as exc:  # includes 429 when the free quota is used up
        raise LLMUnavailable(f"{type(exc).__name__}: {str(exc)[:120]}") from exc
    try:
        parts = r.json()["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, ValueError) as exc:  # e.g. blocked by safety filters
        raise LLMUnavailable("Gemini returned no text") from exc
    return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
