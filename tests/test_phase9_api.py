"""Phase 9: HTTP API contract (FastAPI TestClient - no server needed)."""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fundfacts.config import settings

ROOT = Path(__file__).resolve().parents[1]
built = pytest.mark.skipif(not settings.paths.index_export.exists(), reason="run the ingestion pipeline first")


@pytest.fixture(scope="module")
def client():
    from api.index import app
    return TestClient(app)


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_meta_has_ui_contract(client):
    m = client.get("/api/meta").json()
    assert m["name"] == "FundFacts AI" and len(m["examples"]) == 3 and len(m["schemes"]) == 5
    assert "Facts-only. No investment advice." in m["disclaimer"]
    assert m["llm"]["provider"] in (None, "gemini", "anthropic") and "api_key" not in json.dumps(m)


@pytest.mark.parametrize("payload", [{"message": ""}, {"message": "x" * 501}, {}])
def test_invalid_requests_rejected(client, payload):
    assert client.post("/api/chat", json=payload).status_code == 422


@built
def test_chat_answer_shape(client, monkeypatch):
    monkeypatch.setattr(settings.llm, "provider", "none")
    r = client.post("/api/chat", json={"message": "What is the exit load of HDFC Small Cap Fund?"}).json()
    assert r["type"] == "answer" and r["path"] == "fact"
    assert r["source_url"].startswith("https://files.hdfcfund.com/") and r["last_updated"]
    assert r["evidence"][0]["chunk_id"].endswith("fact_hdfc_small_cap_exit_load")


@built
def test_chat_refusal_has_link_and_no_echo(client):
    r = client.post("/api/chat", json={"message": "My PAN is ABCDE1234F, check my holdings"}).json()
    assert r["type"] == "refusal_pii" and r["source_url"]
    assert "ABCDE1234F" not in json.dumps(r)


def test_ui_has_required_elements():
    html = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
    for needle in ["Facts-only. No investment advice.", "id=\"chips\"", "Last updated from sources", "Why this answer",
                   "/api/chat", "/api/meta", "not affiliated with Groww or HDFC Mutual Fund"]:
        assert needle in html, needle


def test_vercel_bundle_includes_runtime_files():
    cfg = json.loads((ROOT / "vercel.json").read_text())
    inc = cfg["functions"]["api/index.py"]["includeFiles"]
    for f in ["fundfacts/**", "config.yaml", "sources.yaml", "vector_store/index.json", "data/facts/facts.json"]:
        assert f in inc
    req = (ROOT / "requirements.txt").read_text()
    assert "torch" not in req and "sentence-transformers" not in req and "chromadb" not in req


# ------------------------------------------------------------------ Vercel rewrite (/api/x -> /api/index?__route=x)
def test_vercel_rewrite_restores_route(client):
    assert client.get("/api/index?__route=health").json() == {"status": "ok"}
    assert client.get("/api/index?__route=meta").json()["name"] == "FundFacts AI"
    assert client.post("/api/index?__route=chat", json={"message": ""}).status_code == 422  # reached /api/chat


@pytest.mark.parametrize("bad", ["../secret", "a b", "x" * 65])
def test_vercel_rewrite_rejects_odd_routes(client, bad):
    assert client.get(f"/api/index?__route={bad}").status_code == 404


def test_no_debug_route_leaks_headers(client):
    r = client.get("/api/does-not-exist", headers={"x-vercel-oidc-token": "secret"})
    assert r.status_code == 404 and "secret" not in r.text


# ------------------------------------------------------------------ Explore schemes
@built
def test_schemes_endpoint_lists_five_fact_sheets(client):
    s = client.get("/api/schemes").json()["schemes"]
    assert [x["scheme_id"] for x in s] == ["hdfc_large_cap", "hdfc_flexi_cap", "hdfc_elss", "hdfc_small_cap", "hdfc_baf"]
    assert [x["name"] for x in s] == ["HDFC Large Cap Fund", "HDFC Flexi Cap Fund", "HDFC ELSS Tax Saver Fund",
                                      "HDFC Small Cap Fund", "HDFC Balanced Advantage Fund"]
    for x in s:
        assert x["facts"] and x["questions"]
        for f in x["facts"]:  # every shown fact is traceable to an official page
            assert f["value"] and f["source_url"].startswith("https://") and "page" in f["source_title"]
    baf = next(x for x in s if x["scheme_id"] == "hdfc_baf")
    assert "Minimum SIP" in baf["missing"]  # missing facts are listed, never filled
    assert any(f["field"] == "expense_ratio" and "0.75%" in f["value"] for f in baf["facts"])


@built
def test_selected_scheme_applies_to_unnamed_fact_question(client, monkeypatch):
    monkeypatch.setattr(settings.llm, "provider", "none")
    r = client.post("/api/chat", json={"message": "What is the exit load?", "scheme_id": "hdfc_baf"}).json()
    assert r["type"] == "answer" and r["path"] == "fact" and "HDFC Balanced Advantage Fund" in r["text"]


@built
def test_scheme_named_in_question_beats_selection(client, monkeypatch):
    monkeypatch.setattr(settings.llm, "provider", "none")
    r = client.post("/api/chat", json={"message": "Exit load of HDFC Small Cap Fund?", "scheme_id": "hdfc_baf"}).json()
    assert "HDFC Small Cap Fund" in r["text"] and "Balanced Advantage" not in r["text"]


@built
def test_selection_does_not_hijack_concept_or_out_of_scope_questions(client, monkeypatch):
    monkeypatch.setattr(settings.llm, "provider", "none")
    nav = client.post("/api/chat", json={"message": "What is NAV?", "scheme_id": "hdfc_baf"}).json()
    assert "Balanced Advantage" not in nav["text"]
    baf = client.post("/api/chat", json={"message": "Exit load of HDFC Mid Cap Fund?", "scheme_id": "hdfc_baf"}).json()
    assert baf["type"] == "not_found"


@pytest.mark.parametrize("bad", ["HDFC MID", "x" * 41, "../etc"])
def test_scheme_id_is_validated(client, bad):
    assert client.post("/api/chat", json={"message": "exit load?", "scheme_id": bad}).status_code == 422


def test_ui_has_explore_and_theme_toggle():
    html = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
    for needle in ['id="exploreBtn"', 'aria-label="Explore schemes"', 'id="themeBtn"', "/api/schemes", "ff-theme",
                   ':root[data-theme="dark"]', ':root[data-theme="light"]', "scheme_id"]:
        assert needle in html, needle


def test_ui_scheme_scope_and_no_chat_persistence():
    html = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
    assert "mid cap" not in html.lower() and "mid_cap" not in html
    for name in ["HDFC Large Cap Fund", "HDFC Flexi Cap Fund", "HDFC ELSS Tax Saver Fund", "HDFC Small Cap Fund",
                 "HDFC Balanced Advantage Fund"]:
        assert name in html, name
    # chats live in memory only: the theme is the only thing written to browser storage
    assert html.count("localStorage.setItem") == 1 and 'localStorage.setItem("ff-theme"' in html
    assert "sessionStorage" not in html and "indexedDB" not in html
    # badges claim only the checks the backend runs (citation checks), never a blanket 'verified'
    assert "· verified" not in html and "Verified from source" not in html
    assert "grid-template-rows: minmax(0, 1fr)" in html  # composer pinned; thread scrolls above it
    # feedback is visual-only: no request other than the existing endpoints
    assert set(re.findall(r'fetch\("([^"]+)"', html)) == {"/api/chat", "/api/meta", "/api/schemes"}
