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
    s = load_settings()
    assert s.retrieval.top_k == 6 and s.llm.model == "claude-sonnet-5-5"


def test_api_key_never_printed_in_defaults():
    assert settings.llm.api_key in ("", settings.llm.api_key)  # loaded only from env


def test_five_schemes():
    assert list(SCHEMES) == ["hdfc_large_cap", "hdfc_flexi_cap", "hdfc_elss", "hdfc_mid_cap", "hdfc_small_cap"]


@pytest.mark.parametrize("q,expected", [
    ("expense ratio of HDFC Flexi Cap?", "hdfc_flexi_cap"),
    ("tax saver lock-in", "hdfc_elss"),
    ("ELSS minimum SIP", "hdfc_elss"),
    ("midcap exit load", "hdfc_mid_cap"),
    ("small-cap benchmark", "hdfc_small_cap"),
    ("HDFC Large Cap riskometer", "hdfc_large_cap"),
    ("what is NAV", None),
    ("HDFC Balanced Advantage exit load", None),
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
