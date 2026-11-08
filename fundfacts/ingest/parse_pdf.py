"""PDF -> per-page clean text, with performance sections removed.

Rules (see docs/implementation.md, Phase 3):
- Text is extracted page by page with pypdf; whitespace is normalised but line
  breaks are kept so later phases can read "LABEL / value" layouts.
- Performance and returns material is cut out *before* anything is stored:
  returns tables, SIP performance, risk ratios (Sharpe, std. deviation), and
  portfolio holdings. Each cut is recorded in Page.removed.
- For multi-scheme documents (KIM, factsheet) only pages that name one of the
  five in-scope schemes are kept.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from pypdf import PdfReader

logging.getLogger("pypdf").setLevel(logging.ERROR)

# Headings that START a section we must not ingest (case-insensitive, at line start).
CUT_START = [  # matched case-sensitively, so a wrapped sentence ("performance of the Scheme to...") is not a heading
    r"SIP PERFORMANCE",
    r"PERFORMANCE\s*\^",
    r"PERFORMANCE OF THE SCHEME",
    r"Performance of the Scheme",
    r"SCHEME PERFORMANCE",
    r"Scheme performance summary",
    r"Performance details of [Ss]chemes",
    r"For performance details",
    r"QUANTITATIVE DATA",
    r"Risk Ratio",
    r"PORTFOLIO\s*$",
    r"Industry Allocation",
    r"Industry\s+llocation",           # factsheet font drops the 'A'
    r"Absolute [Rr]eturns",
    r"Returns? \(%\)",
    r"CAGR",
]
# A page whose opening lines match one of these is dropped entirely.
DROP_PAGE = re.compile(r"Past performance may or may not be sustained|IDCW HISTORY", re.I)
# Factsheet/KIM annexure pages that are about many schemes (kept when they name an in-scope scheme).
ANNEXURE = re.compile(r"FUND DETAILS ANNEXURE|BENCHMARK AND SCHEME RISKOMETERS|GOAL BASED SOLUTIONS|"
                      r"Funds Managed|PRODUCT LABELING:|NAME & TYPE OF", re.I)
# Headings that END a cut section (facts resume).
CUT_END = [
    r"EXPENSE RATIO",
    r"#?BENCHMARK INDEX",
    r"EXIT LOAD",
    r"FUND MANAGER",
    r"CATEGORY OF SCHEME",
    r"INVESTMENT OBJECTIVE",
    r"MINIMUM APPLICATION",
    r"DATE OF ALLOTMENT",
    r"LOAD STRUCTURE",
    r"PLANS? (AND|&) OPTIONS",
]
_START = re.compile(r"^\s*(" + "|".join(CUT_START) + r")")
_END = re.compile(r"^\s*(" + "|".join(CUT_END) + r")", re.I)


def normalise(text: str) -> str:
    text = text.replace("\xa0", " ").replace("’", "'").replace("ﬀ", "ff").replace("ﬁ", "fi")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    out: list[str] = []
    for ln in lines:
        if not ln:
            continue
        if out and out[-1].endswith("-") and ln[:1].islower():  # re-join hyphenated words
            out[-1] = out[-1][:-1] + ln
        else:
            out.append(ln)
    return "\n".join(out)


# Second layer: individual return-table rows and their footnotes (tables whose heading is split across lines).
RETURN_LINE = re.compile(
    r"^(Returns?\s*(for|since|%|\(%\))|Last\s+\d+\s+(Years?|Months?)\b|Since\s*$|Since\s+Inception|Inception\s*\*?\s*$|"
    r"Period\s+Returns|\(%\)\s*[\^#]|.*Past performance may or may not|sustained in the future|"
    r".*compounded\s+annuali[sz]ed|annuali[sz]ed\s*\(CAGR\)|Returns greater than|Since inception returns are calculated|"
    r"\(allotment price\)|Scheme\s+Benchmark\s*$|Benchmark\s*$|Returns\s*$|\(%\)#?\s*$)",
    re.I,
)
NUMERIC_ROW = re.compile(r"^[\s\d.,%()*^#$-]+$")


def scrub_return_rows(lines: list[str]) -> tuple[list[str], int]:
    kept, dropped, after_return = [], 0, False
    for ln in lines:
        if RETURN_LINE.match(ln) or (after_return and NUMERIC_ROW.match(ln)):
            dropped += 1
            after_return = True
            continue
        after_return = False
        kept.append(ln)
    return kept, dropped


def scrub_performance(text: str) -> tuple[str, list[str]]:
    """Remove performance/returns/portfolio sections. Returns (text, removed headings)."""
    kept, removed, cutting = [], [], False
    for ln in text.splitlines():
        if _START.match(ln):
            cutting = True
            removed.append(ln[:60])
            continue
        if cutting and _END.match(ln):
            cutting = False
        if not cutting:
            kept.append(ln)
    kept, n_rows = scrub_return_rows(kept)
    if n_rows:
        removed.append(f"{n_rows} return-table line(s)")
    return "\n".join(kept), removed


def scheme_mentions(text: str, patterns: dict[str, re.Pattern]) -> list[str]:
    return [sid for sid, pat in patterns.items() if pat.search(text)]


# Names as printed in HDFC documents live in fundfacts/schemes.py (no PDF dependency, so the
# serverless runtime can use them); re-exported here for the ingestion code.
from fundfacts.schemes import DOC_NAME_PATTERNS  # noqa: E402


HDFC_SCHEME_HEADER = re.compile(r"^HDFC\s+\S", re.M)


def page_owner(text: str) -> tuple[list[str], bool]:
    """For one-scheme-per-page layouts: (in-scope schemes in the page header, header names another HDFC scheme).

    Annexure pages (tables covering many schemes) return ([], False) so every mention is kept.
    """
    header = "\n".join(text.splitlines()[:6])
    if ANNEXURE.search(header):
        return [], False
    owners = scheme_mentions(header, DOC_NAME_PATTERNS)
    other = not owners and bool(HDFC_SCHEME_HEADER.search(header)) and not ANNEXURE.search(header)
    return owners, other


def parse_pdf(path: Path, multi_scheme: bool) -> tuple[list[dict], dict, str]:
    """Return (pages, stats, head_text).

    head_text is the raw text of the first two pages (before any filtering), used to find the
    document date. Each kept page: {n, text, scheme_ids, removed}.
    """
    reader = PdfReader(str(path))
    pages, dropped, head = [], {"no_scheme": 0, "performance_page": 0, "other_scheme": 0, "empty": 0}, []
    for i, pg in enumerate(reader.pages, start=1):
        try:
            text = normalise(pg.extract_text() or "")
        except Exception:  # noqa: BLE001 - a broken page must not stop the load
            text = ""
        if i <= 2:
            head.append(text)
        if DROP_PAGE.search("\n".join(text.splitlines()[:4])):
            dropped["performance_page"] += 1
            continue
        schemes = scheme_mentions(text, DOC_NAME_PATTERNS)
        if multi_scheme:
            if not schemes:
                dropped["no_scheme"] += 1
                continue
            owners, other = page_owner(text)
            if other:  # e.g. a fund-of-funds page that merely lists our schemes as holdings
                dropped["other_scheme"] += 1
                continue
            schemes = owners or schemes
        text, removed = scrub_performance(text)
        if len(text) < 40:
            dropped["empty"] += 1
            continue
        pages.append({"n": i, "text": text, "scheme_ids": schemes, "removed": removed})
    stats = {"pdf_pages": len(reader.pages), "kept": len(pages), "dropped": dropped,
             "sections_removed": sum(len(p["removed"]) for p in pages)}
    return pages, stats, "\n".join(head)
