"""Shared LLM types."""


class LLMUnavailable(RuntimeError):
    """No API key, quota exhausted, or the API call failed - the caller falls back to a verified quote."""
