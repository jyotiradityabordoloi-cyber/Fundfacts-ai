"""Phase 3 - Load documents: raw HTML/PDF -> clean Document JSON, page by page.

    python -m fundfacts.ingest.load

Output
    data/docs/<source_id>.json     (fundfacts.schemas.Document)
    data/docs/load_report.json     (pages kept/dropped, sections removed, doc dates)
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime

from fundfacts.config import settings
from fundfacts.ingest.parse_html import parse_html
from fundfacts.ingest.parse_pdf import DOC_NAME_PATTERNS, parse_pdf, scheme_mentions
from fundfacts.schemas import Document, DocType, Page, RawFetch
from fundfacts.sources import load_sources

MULTI_SCHEME = {DocType.KIM, DocType.FACTSHEET}
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE_TXT = rf"(?:\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS}),?\s+\d{{4}}|(?:{MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}})"
DATE_PATTERNS = [  # most specific first
    re.compile(rf"\bdated\s+({DATE_TXT})", re.I),
    re.compile(rf"updated\s+as\s+on\s+({DATE_TXT})", re.I),
    re.compile(rf"\bas\s+on\s+({DATE_TXT})", re.I),
]


def parse_date(s: str) -> date | None:
    s = re.sub(r"(\d)(st|nd|rd|th)", r"\1", s).replace(",", " ")
    s = re.sub(r"\s+", " ", s).strip()
    for fmt in ("%B %d %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s.title(), fmt).date()
        except ValueError:
            continue
    return None


def find_doc_date(head: str, patterns: list[re.Pattern] = DATE_PATTERNS) -> date | None:
    for pat in patterns:
        m = pat.search(head)
        if m and (d := parse_date(m.group(1))):
            return d
    return None


def load_one(src, rec: RawFetch) -> tuple[Document, dict]:
    path = settings.paths.raw / rec.path
    if path.suffix == ".pdf":
        pages, stats, head = parse_pdf(path, multi_scheme=src.doc_type in MULTI_SCHEME)
        doc_date = find_doc_date(head)
    else:
        title, text = parse_html(src.source_id, path.read_text(encoding="utf-8", errors="replace"))
        pages = [{"n": 1, "text": text, "scheme_ids": scheme_mentions(text, DOC_NAME_PATTERNS), "removed": []}]
        stats = {"html_chars": len(text)}
        # web articles: only an explicit "dated"/"updated as on" counts; "as on" in body text is usually an example
        doc_date = find_doc_date(text[:1500], DATE_PATTERNS[:2])
    doc = Document(
        source_id=src.source_id, url=str(src.url), title=src.title, publisher=src.publisher,
        doc_type=src.doc_type, scheme_id=src.scheme_id, fetched_at=rec.fetched_at,
        doc_date=doc_date, pages=[Page(**p) for p in pages],
    )
    return doc, stats


def run() -> list[dict]:
    manifest = {r["source_id"]: RawFetch(**r) for r in
                json.loads((settings.paths.raw / "manifest.json").read_text(encoding="utf-8"))}
    settings.paths.docs.mkdir(parents=True, exist_ok=True)
    report = []
    for src in load_sources():
        rec = manifest.get(src.source_id)
        if rec is None or rec.path is None:
            if src.status.value in ("active", "manual"):
                print(f"[load] skip  {src.source_id:<26} (not fetched: {rec.error if rec else 'no manifest entry'})")
            continue
        doc, stats = load_one(src, rec)
        out = settings.paths.docs / f"{src.source_id}.json"
        out.write_text(doc.model_dump_json(indent=1), encoding="utf-8")
        chars = sum(len(p.text) for p in doc.pages)
        empty = chars < 200
        row = {"source_id": src.source_id, "pages": len(doc.pages), "chars": chars,
               "doc_date": doc.doc_date.isoformat() if doc.doc_date else None, "empty": empty, **stats}
        report.append(row)
        flag = "  <-- almost no text" if empty else ""
        print(f"[load] {src.source_id:<26} pages={len(doc.pages):>3} chars={chars:>7} "
              f"date={row['doc_date'] or '-':<10} {json.dumps(stats)}{flag}")
    (settings.paths.docs / "load_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[load] wrote {len(report)} documents -> {settings.paths.docs}")
    return report


def main() -> None:
    report = run()
    sys.exit(1 if any(r["empty"] for r in report) else 0)


if __name__ == "__main__":
    main()
