"""Phase 2: fetch rules (no network - a fake session is used)."""
import pytest

from fundfacts.config import settings
from fundfacts.ingest import fetch
from fundfacts.schemas import Source


class FakeResp:
    def __init__(self, status=200, content=b"", ctype="text/html"):
        self.status_code, self.content, self.headers = status, content, {"content-type": ctype}


class FakeSession:
    def __init__(self, resp):
        self.resp, self.calls = resp, []

    def get(self, url, **kw):
        self.calls.append(url)
        return self.resp


@pytest.fixture
def tmp_raw(tmp_path, monkeypatch):
    monkeypatch.setattr(settings.paths, "raw", tmp_path)
    return tmp_path


def src(url="https://files.hdfcfund.com/x.pdf"):
    return Source(source_id="t_src", url=url, publisher="AMC", doc_type="SID", title="t")


def test_pdf_saved_with_hash(tmp_raw):
    s = FakeSession(FakeResp(content=b"%PDF-1.7 body", ctype="application/pdf"))
    rec = fetch.fetch_active(src(), s)
    assert rec.path == "t_src.pdf" and len(rec.sha256) == 64
    assert (tmp_raw / "t_src.pdf").read_bytes().startswith(b"%PDF")


def test_html_saved(tmp_raw):
    page = b"<html><a href='https://other.example/'>link</a></html>"
    s = FakeSession(FakeResp(content=page))
    rec = fetch.fetch_active(src("https://investor.sebi.gov.in/elss.html"), s)
    assert rec.path == "t_src.html"
    assert s.calls == ["https://investor.sebi.gov.in/elss.html"]  # exactly one GET, links not followed


def test_http_error_not_saved(tmp_raw):
    rec = fetch.fetch_active(src(), FakeSession(FakeResp(status=403, content=b"Access Denied")))
    assert rec.path is None and rec.error == "HTTP 403"
    assert not list(tmp_raw.iterdir())


def test_fake_pdf_rejected(tmp_raw):
    rec = fetch.fetch_active(src(), FakeSession(FakeResp(content=b"<html>login</html>", ctype="application/pdf")))
    assert rec.path is None and "not one" in rec.error


def test_manual_missing_is_reported(tmp_raw, tmp_path, monkeypatch):
    monkeypatch.setattr(settings.paths, "manual", tmp_path / "manual")
    rec = fetch.copy_manual(src("https://www.hdfcfund.com/services/consolidated-account-statement"))
    assert rec.path is None and "manual file missing" in rec.error


def test_manual_file_copied(tmp_raw, tmp_path, monkeypatch):
    manual = tmp_path / "manual"
    manual.mkdir()
    (manual / "t_src.html").write_text("<html>CAS steps</html>", encoding="utf-8")
    monkeypatch.setattr(settings.paths, "manual", manual)
    rec = fetch.copy_manual(src("https://www.hdfcfund.com/services/consolidated-account-statement"))
    assert rec.path == "t_src.html" and rec.url.startswith("https://www.hdfcfund.com/")
