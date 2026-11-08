"""Phase 4: fact extraction.

Expected values below were hand-checked against the source PDFs (page numbers in comments).
"""
import json
from datetime import datetime, timezone

import pytest

from fundfacts.config import settings
from fundfacts.ingest import extract_facts as ef
from fundfacts.schemas import Document, FactField, Page

FACTS_FILE = settings.paths.facts / "facts.json"
needs_facts = pytest.mark.skipif(not FACTS_FILE.exists(), reason="run `python -m fundfacts.ingest.extract_facts` first")


def facts():
    return {(f["scheme_id"], f["field"]): f for f in json.loads(FACTS_FILE.read_text(encoding="utf-8"))}


EXPECTED = {
    # factsheet Sep 2026, scheme pages 7/11/13/15/62
    ("hdfc_flexi_cap", "expense_ratio"): "Direct Plan 0.67%",
    ("hdfc_large_cap", "expense_ratio"): "Direct Plan 1.00%",
    ("hdfc_mid_cap", "expense_ratio"): "Direct Plan 0.71%",
    ("hdfc_small_cap", "expense_ratio"): "Direct Plan 0.76%",
    ("hdfc_elss", "expense_ratio"): "Direct Plan 1.13%",
    # SIDs dated 21 Nov 2025, p4-p5
    ("hdfc_large_cap", "benchmark"): "NIFTY 100 Total Returns Index (TRI)",
    ("hdfc_mid_cap", "benchmark"): "NIFTY MIDCAP 150 (TRI)",
    ("hdfc_small_cap", "benchmark"): "BSE 250 SmallCap Index (TRI)",
    ("hdfc_elss", "exit_load"): "Nil",
    ("hdfc_mid_cap", "exit_load"): "Exit Load of 1.00% is payable if Units are redeemed/ switched-out within 1 year",
    ("hdfc_elss", "min_lumpsum"): "Rs. 500/- and in multiples of Rs. 500",
    ("hdfc_flexi_cap", "min_lumpsum"): "Rs.100/- and any amount thereafter",
    ("hdfc_elss", "lock_in"): "3 years from the date of allotment",
    # AMFI SSD (HDFC Small Cap), item 5 and 49
    ("hdfc_small_cap", "riskometer"): "Very High Risk",
    ("hdfc_small_cap", "min_sip"): "MSIP - Rs. 100",
    # factsheet annexure p107-108
    ("hdfc_elss", "fund_manager"): "Amar Kalkundrikar",
    ("hdfc_mid_cap", "fund_manager"): "Chirag Setalvad",
}


@needs_facts
@pytest.mark.parametrize("key,expected", list(EXPECTED.items()), ids=[f"{k[0]}:{k[1]}" for k in EXPECTED])
def test_hand_checked_values(key, expected):
    f = facts()[key]
    assert f["status"] == "found", key
    assert expected in f["value"], f["value"]


@needs_facts
def test_every_found_fact_is_traceable():
    for f in facts().values():
        if f["status"] == "found":
            assert f["source_id"] and f["page"] and f["quote"], f
            assert f["source_id"].startswith(("hdfc_", "sebi_", "amfi_"))


@needs_facts
def test_values_are_grounded_in_quotes():
    """Every number in a value must appear in its quote (no invented figures)."""
    import re
    for f in facts().values():
        if f["status"] == "found":
            for num in re.findall(r"\d+(?:\.\d+)?", f["value"]):
                assert num in f["quote"], (f["scheme_id"], f["field"], num, f["quote"])


@needs_facts
def test_non_elss_have_no_lock_in_and_elss_has_three_years():
    fx = facts()
    for sid in ["hdfc_large_cap", "hdfc_flexi_cap", "hdfc_mid_cap", "hdfc_small_cap"]:
        assert fx[(sid, "lock_in")]["value"].startswith("No lock-in")
    assert "3 years" in fx[("hdfc_elss", "lock_in")]["value"]


@needs_facts
def test_fund_manager_role_is_kept_not_merged():
    fx = facts()
    assert "Arun Agarwal" not in fx[("hdfc_mid_cap", "fund_manager")]["value"]
    assert "Bhagyesh Kagalkar (Commodities related investments)" in fx[("hdfc_mid_cap", "fund_manager")]["value"]


# ------------------------------------------------------------------ rules, independent of the corpus
def _fake_doc(source_id, text):
    return Document(source_id=source_id, url="https://example.com/x.pdf", title="t", publisher="AMC", doc_type="SID",
                    fetched_at=datetime.now(timezone.utc), pages=[Page(n=1, text=text)])


def test_missing_source_gives_missing_not_default(monkeypatch):
    monkeypatch.setattr(ef, "doc", lambda sid: None)
    f = ef.extract("hdfc_mid_cap", FactField.MIN_SIP)
    assert f.status == "missing" and f.value is None and f.source_id is None


def test_ssd_sip_split_across_lines(monkeypatch):
    text = "49 SIP SWP & STP Details: Minimum\namount\nFor SIP DSIP, WSIP, MSIP - Rs. 100; QSIP - Rs. 1500. For SWAP Fixed SWAP - Rs. 100"
    monkeypatch.setattr(ef, "doc", lambda sid: _fake_doc(sid, text) if sid.endswith("_ssd") else None)
    f = ef.min_sip_ssd("hdfc_mid_cap")
    assert f and "MSIP - Rs. 100; QSIP - Rs. 1500" in f.value


def test_exit_load_section_bounds(monkeypatch):
    text = "XI. Load Structure\nExit Load:\n- an Exit Load of 1.00% is payable if Units are redeemed within 1\nyear.\n" \
           "In respect of Systematic Transactions such as SIP\nXII. Minimum Application"
    monkeypatch.setattr(ef, "doc", lambda sid: _fake_doc(sid, text))
    f = ef.exit_load_sid("hdfc_mid_cap")
    assert f.value == "an Exit Load of 1.00% is payable if Units are redeemed within 1 year."
