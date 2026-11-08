"""Phase 9: HTTP API contract (FastAPI TestClient - no server needed)."""
import json
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
    assert m["llm"]["provider"] == "anthropic" and "api_key" not in json.dumps(m)


@pytest.mark.parametrize("payload", [{"message": ""}, {"message": "x" * 501}, {}])
def test_invalid_requests_rejected(client, payload):
    assert client.post("/api/chat", json=payload).status_code == 422


@built
def test_chat_answer_shape(client, monkeypatch):
    monkeypatch.setattr(settings.llm, "api_key", "")
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
