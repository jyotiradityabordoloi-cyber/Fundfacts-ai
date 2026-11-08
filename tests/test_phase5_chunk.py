"""Phase 5: chunking rules and checks on the real chunk file."""
import json

import pytest

from fundfacts.config import settings
from fundfacts.ingest.chunk import PAGE_HEADER, pack, paragraphs, split_long
from fundfacts.schemes import SCHEMES


def test_paragraphs_rebuilt_from_wrapped_lines():
    text = "XI. Load Structure\nExit Load:\n• an Exit Load of 1.00% is payable if Units\nare redeemed within 1 year.\nNo lock-in."
    paras = paragraphs(text)
    assert ("XI. Load Structure", "• an Exit Load of 1.00% is payable if Units are redeemed within 1 year.") in paras
    assert paras[0][1].startswith("XI. Load Structure")


@pytest.mark.parametrize("line", ["17", "17 | HDFC Mid Cap Fund-SID", "HDFC Mid Cap Fund-SID", "13 | September 2026",
                                  "HDFC Mutual Fund - Key Information Memorandum Dated November 28, 2025",
                                  "For Product label and Riskometers, refer page no: 124-139"])
def test_running_headers_are_dropped(line):
    assert PAGE_HEADER.match(line)


def test_real_content_is_not_a_header():
    assert not PAGE_HEADER.match("Exit Load of 1.00% is payable if Units are redeemed within 1 year.")


def test_pack_respects_size_and_overlaps():
    paras = [("s", "a" * 300), ("s", "b" * 300), ("s", "c" * 100), ("s", "d" * 300)]
    chunks = pack(paras, size=700, overlap=120)
    assert all(len(t) <= 700 for _, t in chunks)
    assert len(chunks) == 2
    assert chunks[1][1].startswith("c" * 100)  # trailing short paragraph repeated as overlap


def test_split_long_paragraph_on_sentences():
    p = " ".join(f"Sentence number {i} is here." for i in range(60))
    parts = split_long(p, 300)
    assert all(len(x) <= 300 for x in parts) and " ".join(parts) == p


# ------------------------------------------------------------------ real chunk file
CHUNKS = settings.paths.chunks / "chunks.json"
needs = pytest.mark.skipif(not CHUNKS.exists(), reason="run `python -m fundfacts.ingest.chunk` first")


@pytest.fixture(scope="module")
def chunks():
    return json.loads(CHUNKS.read_text(encoding="utf-8"))


@needs
def test_ids_unique_and_texts_non_empty(chunks):
    ids = [c["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids))
    assert all(40 <= len(c["text"]) <= settings.chunking.max_chars for c in chunks if c["kind"] != "fact_card")


@needs
def test_every_found_fact_has_exactly_one_card(chunks):
    facts = json.loads((settings.paths.facts / "facts.json").read_text(encoding="utf-8"))
    cards = [c for c in chunks if c["kind"] == "fact_card"]
    assert len(cards) == sum(f["status"] == "found" for f in facts)
    for card in cards:
        assert card["text"].startswith(SCHEMES[card["scheme_id"]].name)


@needs
def test_pdf_chunks_cite_a_page_and_valid_scheme(chunks):
    for c in chunks:
        assert c["page"] >= 1 and c["url"].startswith("https://")
        assert c["scheme_id"] in (None, *SCHEMES)


@needs
def test_no_performance_text_in_chunks(chunks):
    import re
    perf = re.compile(r"Sharpe|CAGR|Returns? \(%\)|Returns? for last|SIP PERFORMANCE", re.I)
    assert not [c["chunk_id"] for c in chunks if perf.search(c["text"])]
