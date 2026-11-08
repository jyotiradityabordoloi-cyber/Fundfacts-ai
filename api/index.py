"""FundFacts AI - HTTP API (FastAPI). Runs locally with uvicorn and on Vercel as a Python function.

Routes
    GET  /api/health   liveness
    GET  /api/meta     welcome text, example questions, disclaimer, scope, build info
    POST /api/chat     {"message": "..."} (<= 500 chars) -> Answer JSON

Privacy: request bodies are never logged or stored. Uvicorn's access log only records the path.
Locally, the UI in /public is served at "/"; on Vercel the CDN serves it.
"""
from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from fundfacts.config import settings  # noqa: E402
from fundfacts.query.answer import answer  # noqa: E402
from fundfacts.schemas import Answer  # noqa: E402
from fundfacts.schemes import SCHEMES  # noqa: E402

WELCOME = "Hi, I'm FundFacts AI. Ask me factual questions about five HDFC Mutual Fund schemes - every answer cites one official source."
EXAMPLES = [
    "What is the expense ratio of HDFC Mid Cap Fund?",
    "What is the lock-in period of HDFC ELSS Tax Saver?",
    "What is the exit load of HDFC Small Cap Fund?",
]
DISCLAIMER = ("Facts-only. No investment advice. Answers come only from official HDFC Mutual Fund, SEBI and AMFI "
              "documents. Mutual fund investments are subject to market risks; read all scheme-related documents "
              "carefully. Independent student project, not affiliated with Groww or HDFC Mutual Fund.")

app = FastAPI(title="FundFacts AI", version="1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=settings.answer.max_question_chars)


@lru_cache(maxsize=1)
def _build_info() -> dict:
    try:
        data = json.loads(settings.paths.index_export.read_text(encoding="utf-8"))
        sources = {c["source_id"] for c in data["chunks"]}
        return {"built_at": data.get("built_at"), "chunks": data["count"], "sources": len(sources)}
    except FileNotFoundError:
        return {}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    return {
        "name": "FundFacts AI",
        "welcome": WELCOME,
        "examples": EXAMPLES,
        "disclaimer": DISCLAIMER,
        "schemes": [s.name for s in SCHEMES.values()],
        "llm": {"provider": settings.llm.active, "model": settings.llm.model, "enabled": settings.llm.enabled},
        "embedding_model": settings.embedding.model,
        "build": _build_info(),
    }


@app.post("/api/chat", response_model=Answer)
def chat(body: ChatIn):
    return answer(body.message)


@app.exception_handler(Exception)
async def unexpected(request, exc):  # never leak internals (or the question) in an error
    return JSONResponse(status_code=500, content={"type": "error", "text": "Something went wrong. Please try again."})


# Local development: serve the UI from /public (Vercel's CDN does this in production).
_public = ROOT / "public"
if _public.exists() and not os.getenv("VERCEL"):
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_public), html=True), name="ui")
