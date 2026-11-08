"""Phase 2 - Scrape: download exactly the registered sources, nothing else.

    python -m fundfacts.ingest.fetch

Rules
- Only sources.yaml entries with status `active` are downloaded (one GET each).
  Links inside pages are never followed.
- `manual` entries are copied from data/manual/<source_id>.* (the owner saves them
  in a browser because www.hdfcfund.com blocks automated requests).
- `blocked` / `historical` entries are recorded in the manifest and skipped.

Output
    data/raw/<source_id>.html | .pdf
    data/raw/manifest.json      (one RawFetch record per registry entry)
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from datetime import datetime, timezone

import requests

from fundfacts.config import settings
from fundfacts.schemas import RawFetch, Source, SourceStatus
from fundfacts.sources import load_sources, manual_file

PDF_MAGIC = b"%PDF"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _is_pdf(content: bytes, content_type: str, url: str) -> bool:
    return content.startswith(PDF_MAGIC) or "pdf" in content_type.lower() or url.lower().split("?")[0].endswith(".pdf")


def _save(source_id: str, content: bytes, pdf: bool) -> str:
    raw_dir = settings.paths.raw
    for old in raw_dir.glob(f"{source_id}.*"):  # remove a previous copy with another extension
        old.unlink()
    path = raw_dir / f"{source_id}.{'pdf' if pdf else 'html'}"
    path.write_bytes(content)
    return path.name


def fetch_active(src: Source, session: requests.Session) -> RawFetch:
    url = str(src.url)
    try:
        resp = session.get(url, timeout=settings.scrape.timeout_s, allow_redirects=True)
    except requests.RequestException as exc:
        return RawFetch(source_id=src.source_id, url=url, http_status="error", fetched_at=_now(),
                        error=f"{type(exc).__name__}: {str(exc)[:160]}")
    ctype = resp.headers.get("content-type", "").split(";")[0]
    rec = RawFetch(source_id=src.source_id, url=url, http_status=resp.status_code, fetched_at=_now(), content_type=ctype)
    if resp.status_code != 200 or not resp.content:
        rec.error = f"HTTP {resp.status_code}"
        return rec
    pdf = _is_pdf(resp.content, ctype, url)
    if pdf and not resp.content.startswith(PDF_MAGIC):
        rec.error = "expected a PDF but the response is not one"
        return rec
    rec.sha256 = hashlib.sha256(resp.content).hexdigest()
    rec.path = _save(src.source_id, resp.content, pdf)
    return rec


def copy_manual(src: Source) -> RawFetch:
    f = manual_file(src)
    if f is None:
        return RawFetch(source_id=src.source_id, url=str(src.url), http_status="manual", fetched_at=_now(),
                        error=f"manual file missing: save the page as data/manual/{src.source_id}.html")
    content = f.read_bytes()
    pdf = content.startswith(PDF_MAGIC)
    # retrieval date = when the owner saved the file
    saved_at = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).replace(microsecond=0)
    return RawFetch(source_id=src.source_id, url=str(src.url), http_status="manual", fetched_at=saved_at,
                    content_type="application/pdf" if pdf else "text/html",
                    sha256=hashlib.sha256(content).hexdigest(), path=_save(src.source_id, content, pdf))


def run() -> list[RawFetch]:
    settings.paths.raw.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": settings.scrape.user_agent, "Accept-Language": "en-IN,en;q=0.9"})
    manifest: list[RawFetch] = []
    for src in load_sources():
        if src.status == SourceStatus.ACTIVE:
            rec = fetch_active(src, session)
            time.sleep(settings.scrape.delay_s)
        elif src.status == SourceStatus.MANUAL:
            rec = copy_manual(src)
        else:
            rec = RawFetch(source_id=src.source_id, url=str(src.url), http_status=src.status.value,
                           fetched_at=_now(), error=f"skipped ({src.status.value})")
        size = (settings.paths.raw / rec.path).stat().st_size if rec.path else 0
        state = rec.path or rec.error
        print(f"[fetch] {str(rec.http_status):<10} {src.source_id:<26} {size / 1024:>8.0f} KB  {state}")
        manifest.append(rec)

    out = settings.paths.raw / "manifest.json"
    out.write_text(json.dumps([m.model_dump(mode="json") for m in manifest], indent=2), encoding="utf-8")
    saved = sum(1 for m in manifest if m.path)
    expected = sum(1 for s in load_sources() if s.status in (SourceStatus.ACTIVE, SourceStatus.MANUAL))
    print(f"[fetch] saved {saved}/{expected} corpus sources -> {settings.paths.raw}")
    return manifest


def main() -> None:
    manifest = run()
    failed = [m for m in manifest if m.path is None and m.http_status not in ("blocked", "historical", "manual")]
    pending = [m.source_id for m in manifest if m.path is None and m.http_status == "manual"]
    if pending:
        print(f"[fetch] WARNING: manual files still needed in data/manual/: {', '.join(pending)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
