"""Load and validate config.yaml, apply environment overrides.

Usage:
    from fundfacts.config import settings
    python -m fundfacts.config        # print the validated configuration (secrets masked)
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]

try:  # optional at runtime
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


class Paths(BaseModel):
    sources: Path
    raw: Path
    manual: Path
    docs: Path
    facts: Path
    chunks: Path
    embeddings: Path
    chroma: Path
    index_export: Path
    build_report: Path

    def resolved(self) -> "Paths":
        return Paths(**{k: (ROOT / v) for k, v in self.model_dump().items()})


class Scrape(BaseModel):
    timeout_s: int = Field(30, gt=0)
    delay_s: float = Field(0.5, ge=0)
    user_agent: str


class Chunking(BaseModel):
    size: int = Field(700, gt=100)
    overlap: int = Field(120, ge=0)
    max_chars: int = Field(1600, gt=100)


class Embedding(BaseModel):
    model: str
    backend: Literal["auto", "sentence-transformers", "onnx"] = "auto"
    dim: int = 384


class VectorDB(BaseModel):
    backend: Literal["auto", "chroma", "json"] = "auto"
    collection: str = "fundfacts"


class Retrieval(BaseModel):
    top_k: int = Field(4, ge=1, le=20)
    min_similarity: float = Field(0.25, ge=0, le=1)
    scheme_boost: float = 0.08
    phrase_bonus: float = 0.06
    phrase_bonus_cap: float = 0.12


class LLM(BaseModel):
    provider: Literal["auto", "gemini", "anthropic", "none"] = "auto"
    gemini_model: str = "gemini-flash-latest"
    anthropic_model: str = "claude-haiku-5-5"
    temperature: float = Field(0.1, ge=0, le=1)
    max_tokens: int = Field(400, gt=0)
    timeout_s: int = Field(30, gt=0)
    gemini_api_key: str = ""     # from GEMINI_API_KEY only (free tier: aistudio.google.com)
    anthropic_api_key: str = ""  # from ANTHROPIC_API_KEY only

    @property
    def active(self) -> str | None:
        """The provider that will actually be used, or None (free mode: facts + verified quotes)."""
        if self.provider == "none":
            return None
        if self.provider in ("auto", "gemini") and self.gemini_api_key:
            return "gemini"
        if self.provider in ("auto", "anthropic") and self.anthropic_api_key:
            return "anthropic"
        return None

    @property
    def enabled(self) -> bool:
        return self.active is not None

    @property
    def model(self) -> str | None:
        return {"gemini": self.gemini_model, "anthropic": self.anthropic_model}.get(self.active or "")


class Answer(BaseModel):
    max_sentences: int = Field(3, ge=1, le=3)
    max_question_chars: int = Field(500, gt=0)
    timezone_offset_minutes: int = 330


class Settings(BaseModel):
    paths: Paths
    scrape: Scrape
    chunking: Chunking
    embedding: Embedding
    vector_db: VectorDB
    retrieval: Retrieval
    llm: LLM
    answer: Answer


# environment variable -> (section, key)
ENV_OVERRIDES = {
    "EMBEDDING_MODEL": ("embedding", "model"),
    "EMBEDDING_BACKEND": ("embedding", "backend"),
    "VECTOR_DB": ("vector_db", "backend"),
    "TOP_K": ("retrieval", "top_k"),
    "MIN_SIMILARITY": ("retrieval", "min_similarity"),
    "LLM_PROVIDER": ("llm", "provider"),
    "GEMINI_MODEL": ("llm", "gemini_model"),
    "GEMINI_API_KEY": ("llm", "gemini_api_key"),
    "CLAUDE_MODEL": ("llm", "anthropic_model"),
    "ANTHROPIC_API_KEY": ("llm", "anthropic_api_key"),
}


def load_settings(path: Path | None = None) -> Settings:
    raw = yaml.safe_load((path or ROOT / "config.yaml").read_text(encoding="utf-8"))
    for env, (section, key) in ENV_OVERRIDES.items():
        if os.getenv(env):
            raw.setdefault(section, {})[key] = os.environ[env]
    s = Settings(**raw)
    s.paths = s.paths.resolved()
    if s.chunking.overlap >= s.chunking.size:
        raise ValueError("chunking.overlap must be smaller than chunking.size")
    return s


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


settings = get_settings()


if __name__ == "__main__":
    dump = settings.model_dump(mode="json")
    for k in ("gemini_api_key", "anthropic_api_key"):
        dump["llm"][k] = "set" if getattr(settings.llm, k) else "not set"
    dump["llm"]["active_provider"] = settings.llm.active or "none (free mode: exact facts + verified quotes)"
    print(yaml.safe_dump(dump, sort_keys=False))
