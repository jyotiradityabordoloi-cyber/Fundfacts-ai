"""Phase 3: loading rules - performance scrubbing, page ownership, dates, HTML cleaning."""
import glob
import json
import re
from datetime import date

import pytest

from fundfacts.config import settings
from fundfacts.ingest.load import DATE_PATTERNS, find_doc_date, parse_date
from fundfacts.ingest.parse_html import parse_html
from fundfacts.ingest.parse_pdf import normalise, page_owner, scrub_performance

FACTSHEET_PAGE = """13 | September 2026
HDFC Mid Cap Fund
CATEGORY OF SCHEME
MID CAP FUND
QUANTITATIVE DATA
Risk Ratio
Sharpe Ratio* 0.604
EXPENSE RATIO
Regular: 1.26% Direct: 0.71%
#BENCHMARK INDEX
NIFTY MIDCAP 150 (TRI)
PORTFOLIO
The Federal Bank Ltd. Banks 3.98
SIP PERFORMANCE ^ - Regular Plan - Growth Option
Returns (%) 18.47 18.43
EXIT LOAD$$
Exit Load of 1.00% is payable if Units are redeemed within 1 year"""


def test_scrub_keeps_facts_removes_performance():
    text, removed = scrub_performance(FACTSHEET_PAGE)
    for fact in ["Direct: 0.71%", "NIFTY MIDCAP 150 (TRI)", "Exit Load of 1.00%", "MID CAP FUND"]:
        assert fact in text
    for perf in ["Sharpe", "Federal Bank", "18.47", "SIP PERFORMANCE"]:
        assert perf not in text
    assert removed


def test_split_return_table_rows_removed():
    page = "Period Returns\n(%)^\nLast 1 Year -1.56 -9.75\nLast 3 Years 22.42 21.65\nSince\nInception*\n16.26 11.01\n" \
           "Returns greater than one year are compounded\nannualized (CAGR).\nExit Load : Nil"
    text, _ = scrub_performance(page)
    assert text.strip() == "Exit Load : Nil"


def test_wrapped_sentence_is_not_a_heading():
    page = "The fund manager may invest in other schemes and the\nperformance of the Scheme to the extent of investment\nin such schemes will depend on them."
    text, removed = scrub_performance(page)
    assert "to the extent of investment" in text and not removed


@pytest.mark.parametrize("header,owners,other", [
    ("13 | September 2026\nHDFC Mid Cap Fund\nAn open ended equity scheme", ["hdfc_mid_cap"], False),
    ("For Product label and Riskometers, refer page no: 124-139\n58 | September 2026\nHDFC Multi-Asset Active FOF", [], True),
    ("FUND DETAILS ANNEXURE\n104 | September 2026\nHDFC Flexi Cap Fund", [], False),
])
def test_page_owner(header, owners, other):
    assert page_owner(header) == (owners, other)


@pytest.mark.parametrize("s,expected", [
    ("November 21, 2025", date(2025, 11, 21)),
    ("28th November 2025", date(2025, 11, 28)),
    ("September 30, 2026", date(2026, 9, 30)),
    ("31st February 2025", None),
])
def test_parse_date(s, expected):
    assert parse_date(s) == expected


def test_doc_date_prefers_dated_over_as_on():
    head = "NAV as on March 31, 2025.\nThis Key Information Memorandum is dated November 28, 2025."
    assert find_doc_date(head) == date(2025, 11, 28)


def test_html_article_ignores_example_as_on():
    assert find_doc_date("NAV of the scheme as on June 30, 2009 was Rs 10", DATE_PATTERNS[:2]) is None


def test_normalise_rejoins_hyphenation():
    assert normalise("invest-\nment   in  equity") == "investment in equity"


def test_html_trim_and_dedupe():
    html = """<html><body><nav>Home</nav><main>
      <p>Banner text repeated</p><h1>Expense Ratio</h1>
      <p>TER is the ratio of <a href='#'>expenses</a> to assets.</p><p>Banner text repeated</p>
      <p>Related Articles</p><p>Unrelated teaser</p></main></body></html>"""
    title, text = parse_html("amfi_expense_ratio", html)
    assert title == "Expense Ratio"
    assert "TER is the ratio of expenses to assets." in text
    assert text.count("Banner text repeated") == 1 and "Unrelated teaser" not in text


# ------------------------------------------------------- checks on the real loaded corpus
DOCS = sorted(glob.glob(str(settings.paths.docs / "*.json")))
needs_docs = pytest.mark.skipif(len(DOCS) < 10, reason="run `python -m fundfacts.ingest.load` first")
PERF = re.compile(r"Sharpe|Standard Deviation|CAGR|Returns? \(%\)|Returns? for last|Last \d+ Years? -?\d|SIP PERFORMANCE", re.I)


@needs_docs
def test_no_performance_text_in_amc_docs():
    for f in DOCS:
        if not f.endswith("load_report.json") and "hdfc_" in f:
            d = json.load(open(f, encoding="utf-8"))
            assert not any(PERF.search(p["text"]) for p in d["pages"]), d["source_id"]


@needs_docs
def test_every_sid_loaded_with_date():
    for sid in ["hdfc_large_cap", "hdfc_flexi_cap", "hdfc_elss", "hdfc_mid_cap", "hdfc_small_cap"]:
        d = json.load(open(settings.paths.docs / f"{sid}_sid.json", encoding="utf-8"))
        assert d["doc_date"] == "2025-11-21" and len(d["pages"]) > 50
