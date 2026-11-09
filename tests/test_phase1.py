"""Phase 1: configuration, schemas, scheme registry and source registry."""
import pytest
from pydantic import ValidationError

from fundfacts.config import load_settings, settings
from fundfacts.schemas import Answer, AnswerType, Fact, FactField, Source
from fundfacts.schemes import SCHEMES, detect_scheme
from fundfacts.sources import corpus, load_sources


def test_config_loads_and_resolves_paths():
    s = load_settings()
    assert s.embedding.model == "sentence-transformers/all-MiniLM-L6-v2"
    assert s.answer.max_sentences == 3
    assert s.paths.sources.is_absolute()


def test_env_override(monkeypatch):
    monkeypatch.setenv("TOP_K", "6")
    monkeypatch.setenv("CLAUDE_MODEL", "claude-sonnet-5-5")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
    s = load_settings()
    assert s.retrieval.top_k == 6 and s.llm.anthropic_model == "claude-sonnet-5-5" and s.llm.gemini_model == "gemini-2.0-flash"


def test_api_keys_come_only_from_env():
    import yaml
    raw = yaml.safe_load((settings.paths.sources.parent / "config.yaml").read_text(encoding="utf-8"))
    assert not any("api_key" in k for k in raw["llm"])  # keys are never in config.yaml


def test_five_schemes():
    assert list(SCHEMES) == ["hdfc_large_cap", "hdfc_flexi_cap", "hdfc_elss", "hdfc_small_cap", "hdfc_baf"]
    assert [s.name for s in SCHEMES.values()] == ["HDFC Large Cap Fund", "HDFC Flexi Cap Fund", "HDFC ELSS Tax Saver Fund",
                                                  "HDFC Small Cap Fund", "HDFC Balanced Advantage Fund"]


@pytest.mark.parametrize("q,expected", [
    ("expense ratio of HDFC Flexi Cap?", "hdfc_flexi_cap"),
    ("tax saver lock-in", "hdfc_elss"),
    ("ELSS minimum SIP", "hdfc_elss"),
    ("balanced advantage exit load", "hdfc_baf"),
    ("BAF benchmark", "hdfc_baf"),
    ("midcap exit load", None),
    ("small-cap benchmark", "hdfc_small_cap"),
    ("HDFC Large Cap riskometer", "hdfc_large_cap"),
    ("what is NAV", None),
    ("HDFC Mid Cap exit load", None),
])
def test_detect_scheme(q, expected):
    assert detect_scheme(q) == expected


def test_registry_is_valid_and_in_range():
    sources = load_sources()
    c = corpus(sources)
    assert 15 <= len(c) <= 25
    assert {s.publisher.value for s in c} <= {"AMC", "SEBI", "AMFI"}
    for sid in SCHEMES:  # every scheme has its own SID
        assert any(s.scheme_id == sid and s.doc_type.value == "SID" for s in c), sid


def test_source_rejects_bad_id():
    with pytest.raises(ValidationError):
        Source(source_id="Bad ID!", url="https://example.com", publisher="AMC", doc_type="SID", title="x")


def test_fact_and_answer_models():
    f = Fact(scheme_id="hdfc_elss", field=FactField.LOCK_IN, status="found", value="3 years",
             source_id="hdfc_elss_sid", page=4, quote="lock-in period of 3 years")
    assert f.field == FactField.LOCK_IN
    a = Answer(type=AnswerType.NOT_FOUND, text="Not in my sources.")
    assert a.evidence == [] and a.source_url is None


# ------------------------------------------------------------------ inventory reconciliation
INVENTORY = [f"SRC-{i:03d}" for i in range(1, 25)]
EXPECTED_CORPUS = {
    "hdfc_large_cap_sid", "hdfc_flexi_cap_sid", "hdfc_elss_sid", "hdfc_small_cap_sid", "hdfc_baf_sid",
    "hdfc_common_equity_kim", "hdfc_factsheet_sep_2026", "hdfc_small_cap_ssd", "hdfc_request_statement", "hdfc_cas",
    "sebi_mf_faq", "sebi_elss", "sebi_investor_charter", "amfi_intro_mf", "amfi_types", "amfi_expense_ratio",
    "amfi_nav", "amfi_categorization", "amfi_risk", "amfi_booklet",
}


def test_every_inventory_entry_has_exactly_one_decision():
    refs = [s.inventory_ref for s in load_sources() if s.inventory_ref]
    assert sorted(refs) == INVENTORY, sorted(set(INVENTORY) - set(refs))


def test_blocked_inventory_entries_name_their_replacement():
    sources = load_sources()
    ingested = {s.source_id for s in corpus(sources)}
    for s in sources:
        if s.status.value == "blocked":
            stand_ins = [x for x in sources if s.inventory_ref in x.replaces]
            assert stand_ins and all(x.source_id in ingested for x in stand_ins), s.source_id


def test_non_ingested_entries_explain_why_and_when_checked():
    for s in load_sources():
        if s.status.value in ("blocked", "excluded"):
            assert s.notes and s.checked_on, s.source_id


def test_corpus_is_exactly_the_agreed_twenty_official_sources():
    c = corpus()
    assert {s.source_id for s in c} == EXPECTED_CORPUS
    hosts = {str(s.url).split("/")[2] for s in c}
    assert hosts <= {"files.hdfcfund.com", "www.hdfcfund.com", "portal.amfiindia.com", "www.amfiindia.com",
                     "www.sebi.gov.in", "investor.sebi.gov.in"}
    assert not any("groww" in str(s.url) for s in load_sources())


def test_sources_md_matches_registry():
    md = (settings.paths.sources.parent / "SOURCES.md").read_text(encoding="utf-8")
    for s in load_sources():
        assert str(s.url) in md, s.source_id
    assert "UNACCOUNTED" not in md and "groww.in" not in md and "Mid Cap" not in md
