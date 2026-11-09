"""Data contracts shared by ingestion and serving (see docs/architecture.md §4)."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


# ------------------------------------------------------------------ sources
class Publisher(str, Enum):
    AMC = "AMC"
    SEBI = "SEBI"
    AMFI = "AMFI"


class DocType(str, Enum):
    KIM = "KIM"
    SID = "SID"
    FACTSHEET = "factsheet"
    SSD = "SSD"                # AMFI/AMC Scheme Summary Document
    FAQ = "FAQ"
    ARTICLE = "article"
    CIRCULAR = "circular"
    GUIDE = "guide"


class SourceStatus(str, Enum):
    ACTIVE = "active"          # fetched automatically
    MANUAL = "manual"          # owner downloads into data/manual/; URL stays the citation
    BLOCKED = "blocked"        # not fetchable, not ingested
    HISTORICAL = "historical"  # superseded, excluded from the corpus


class Source(BaseModel):
    source_id: str = Field(pattern=r"^[a-z0-9_]+$")
    url: HttpUrl
    publisher: Publisher
    doc_type: DocType
    title: str
    scheme_id: str | None = None
    status: SourceStatus = SourceStatus.ACTIVE
    notes: str = ""


# ------------------------------------------------------------------ ingestion
class RawFetch(BaseModel):
    source_id: str
    url: str
    http_status: int | str
    fetched_at: datetime
    content_type: str = ""
    sha256: str = ""
    path: str | None = None
    error: str | None = None


class Page(BaseModel):
    n: int = Field(ge=1)
    text: str
    scheme_ids: list[str] = []      # in-scope schemes named on this page
    removed: list[str] = []         # sections cut out (e.g. performance tables), for transparency


class Document(BaseModel):
    source_id: str
    url: str
    title: str
    publisher: Publisher
    doc_type: DocType
    scheme_id: str | None = None
    fetched_at: datetime
    doc_date: date | None = None  # "as on" date printed in the document
    pages: list[Page]


class FactField(str, Enum):
    EXPENSE_RATIO = "expense_ratio"
    EXIT_LOAD = "exit_load"
    MIN_SIP = "min_sip"
    MIN_LUMPSUM = "min_lumpsum"
    LOCK_IN = "lock_in"
    RISKOMETER = "riskometer"
    BENCHMARK = "benchmark"
    FUND_MANAGER = "fund_manager"
    CATEGORY = "category"
    OBJECTIVE = "objective"


class Fact(BaseModel):
    scheme_id: str
    field: FactField
    status: Literal["found", "missing"]
    value: str | None = None
    as_of: date | None = None
    source_id: str | None = None
    page: int | None = None
    quote: str | None = None  # verbatim text the value was taken from


class Chunk(BaseModel):
    chunk_id: str
    source_id: str
    scheme_id: str | None = None
    page: int | None = None
    section: str = ""
    kind: Literal["fact_card", "pdf", "prose"]
    text: str
    char_span: tuple[int, int] | None = None


# ------------------------------------------------------------------ serving
class AnswerType(str, Enum):
    ANSWER = "answer"
    REFUSAL_ADVICE = "refusal_advice"
    REFUSAL_RETURNS = "refusal_returns"
    REFUSAL_PII = "refusal_pii"
    NOT_FOUND = "not_found"


class Evidence(BaseModel):
    chunk_id: str
    score: float
    quote: str
    adjustments: dict[str, float] = {}


class Answer(BaseModel):
    type: AnswerType
    text: str
    source_url: str | None = None
    source_title: str | None = None
    last_updated: str | None = None  # e.g. "09 Nov 2026" (IST)
    evidence: list[Evidence] = []
    path: Literal["fact", "rag", "guardrail", "none"] = "none"
    writer: str | None = None            # "fact table", "gemini", "anthropic" or "quote" (verbatim sentence)
    fallback_reason: str | None = None   # why an LLM answer was not used (no secrets, no question text)
