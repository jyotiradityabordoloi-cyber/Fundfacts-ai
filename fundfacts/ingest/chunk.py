"""Phase 5 - Chunking.

    python -m fundfacts.ingest.chunk

Strategy (docs/architecture.md §2.1):
- facts.json  -> one FACT CARD per found fact. One card = one fact = one source page, so the
                 citation of a card is always exact. Cards start with the scheme name and include
                 common synonyms of the field ("TER", "lock-in") to help retrieval.
- PDF pages   -> lines are rebuilt into paragraphs, then packed up to `chunking.size` characters with
                 ~`chunking.overlap` characters of trailing paragraphs repeated. A chunk NEVER
                 crosses a page, so every PDF chunk can cite its page number.
- HTML pages  -> the same paragraph packing on the single logical page.
- Repeated page headers ("17 | HDFC Mid Cap Fund-SID") are removed; identical paragraphs
  shared by several SIDs (common legal/procedural text) are kept once and marked scheme-neutral.

Output
    data/chunks/chunks.json        list[Chunk] (+ title, url, publisher, doc_date, fetched_at)
    data/chunks/chunk_report.json  counts per source and kind
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter

from fundfacts.config import settings
from fundfacts.schemas import Chunk, Document, Fact
from fundfacts.schemes import PLAN_LABEL, SCHEMES
from fundfacts.sources import load_sources

FIELD_LABELS = {
    "expense_ratio": "Expense ratio (TER, total expense ratio)",
    "exit_load": "Exit load (charge on redemption)",
    "min_sip": "Minimum SIP amount (systematic investment plan instalment)",
    "min_lumpsum": "Minimum investment / minimum application amount (lumpsum)",
    "lock_in": "Lock-in period",
    "riskometer": "Riskometer (risk level)",
    "benchmark": "Benchmark index",
    "fund_manager": "Fund manager(s)",
    "category": "Scheme category (SEBI)",
    "objective": "Investment objective",
}
PAGE_HEADER = re.compile(  # running headers/footers repeated on every page of a PDF
    r"^\s*\d{1,3}\s*$"                                                    # bare page number
    r"|^\s*(\d{1,3}\s*\|?\s*)?HDFC [^|]{3,80}?-\s*(SID|KIM)\s*$"          # "17 | HDFC Mid Cap Fund-SID"
    r"|^\s*\d{1,3}\s*\|\s*[A-Z][a-z]+ \d{4}\s*$"                          # "13 | September 2026"
    r"|^HDFC Mutual Fund - Key Information Memorandum Dated .*$"
    r"|^For Product label and Riskometers, refer page no.*$"
    r"|^Page \d+(\s*Fields SCHEME SUMMARY DOCUMENT)?$|^Fields SCHEME SUMMARY DOCUMENT$",
    re.I,
)
# Printed scale of riskometer dials (images) - text with no meaning on its own.
RISKOMETER_DIAL = re.compile(r"^(RISKOMETER|Low Risk|Low to Moderate Risk|Moderate Risk( Moderately High Risk)?|"
                             r"Moderately High Risk|High Risk|Very High Risk|The risk of the (Benchmark|Scheme) is [A-Za-z ]+)$")
HEADING = re.compile(r"^([IVXL]+\.\s+\S.*|[A-Z][A-Z0-9 &/,()'-]{5,60})$")
END_PUNCT = re.compile(r"[.:;?!)]$")


# ------------------------------------------------------------------ text helpers
def paragraphs(text: str) -> list[tuple[str, str]]:
    """Rebuild PDF/HTML lines into (section, paragraph) pairs."""
    paras: list[tuple[str, str]] = []
    section, buf = "", []

    def flush():
        if buf:
            paras.append((section, re.sub(r"\s+", " ", " ".join(buf)).strip()))
            buf.clear()

    for line in text.splitlines():
        line = line.strip()
        if not line or PAGE_HEADER.match(line) or RISKOMETER_DIAL.match(line):
            continue
        if HEADING.match(line) and len(line) < 70:
            flush()
            section = line[:70]
            buf.append(line)
            continue
        if line.startswith(("•", "➢", "- ", "– ")):  # a bullet starts a new paragraph
            flush()
        buf.append(line)
        if END_PUNCT.search(line):
            flush()
    flush()
    return [(s, p) for s, p in paras if len(p) > 2]


def split_long(p: str, size: int) -> list[str]:
    """Paragraphs longer than `size` are split on sentence boundaries (hard cut as a last resort)."""
    if len(p) <= size:
        return [p]
    out, cur = [], ""
    for sent in re.split(r"(?<=[.;?!])\s+", p):
        while len(sent) > size:
            out.append(sent[:size])
            sent = sent[size:]
        if cur and len(cur) + len(sent) + 1 > size:
            out.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        out.append(cur)
    return out


def pack(paras: list[tuple[str, str]], size: int, overlap: int) -> list[tuple[str, str]]:
    """Pack paragraphs into chunks <= size chars; repeat trailing paragraphs (<= overlap chars)."""
    items = [(s, piece) for s, p in paras for piece in split_long(p, size)]
    chunks, cur = [], []
    for item in items:
        if cur and len(" ".join(t for _, t in cur + [item])) > size:
            chunks.append((cur[0][0], " ".join(t for _, t in cur)))
            tail, tail_len = [], 0
            for prev in reversed(cur):
                if tail_len + len(prev[1]) > overlap:
                    break
                tail.insert(0, prev)
                tail_len += len(prev[1])
            cur = tail
        cur.append(item)
    if cur:
        chunks.append((cur[0][0], " ".join(t for _, t in cur)))
    return chunks


def fmt_date(d) -> str:
    return d.strftime("%d %b %Y") if d else ""


# ------------------------------------------------------------------ builders
def fact_cards(facts: list[Fact], docs: dict[str, Document]) -> list[dict]:
    cards = []
    for f in facts:
        if f.status != "found":
            continue
        d = docs[f.source_id]
        scheme = SCHEMES[f.scheme_id].name
        as_of = f" (as on {fmt_date(f.as_of)})" if f.as_of else ""
        text = (f"{scheme} ({PLAN_LABEL}) - {FIELD_LABELS[f.field.value]}: {f.value}{as_of}. "
                f"Source: {d.title}, page {f.page}.")
        cards.append(dict(chunk_id=f"{f.source_id}::p{f.page}::fact_{f.scheme_id}_{f.field.value}",
                          source_id=f.source_id, scheme_id=f.scheme_id, page=f.page, section=f.field.value,
                          kind="fact_card", text=text, field=f.field.value))
    return cards


def doc_chunks(d: Document) -> list[dict]:
    size, overlap = settings.chunking.size, settings.chunking.overlap
    out = []
    for p in d.pages:
        page_scheme = d.scheme_id or (p.scheme_ids[0] if len(p.scheme_ids) == 1 else None)
        for i, (section, body) in enumerate(pack(paragraphs(p.text), size, overlap)):
            if len(body) < 40:
                continue
            start = p.text.find(body[:30])
            out.append(dict(chunk_id=f"{d.source_id}::p{p.n}::{i:02d}", source_id=d.source_id, scheme_id=page_scheme,
                            page=p.n, section=section, kind="pdf" if d.pages[-1].n > 1 or d.url.endswith(".pdf") else "prose",
                            text=body, char_span=(start, start + len(body)) if start >= 0 else None))
    return out


def dedupe(chunks: list[dict]) -> tuple[list[dict], int]:
    """Identical text in several documents (shared SID boilerplate): keep the first, make it scheme-neutral."""
    seen: dict[str, dict] = {}
    kept, dropped = [], 0
    for c in chunks:
        if c["kind"] == "fact_card":
            kept.append(c)
            continue
        key = hashlib.sha1(re.sub(r"HDFC [A-Za-z &-]+?(Fund|Saver)", "HDFC_SCHEME", c["text"]).encode()).hexdigest()
        if key in seen:
            if seen[key]["scheme_id"] != c["scheme_id"]:
                seen[key]["scheme_id"] = None
            dropped += 1
            continue
        seen[key] = c
        kept.append(c)
    return kept, dropped


def run() -> list[dict]:
    titles = {s.source_id: s for s in load_sources()}
    docs: dict[str, Document] = {}
    for path in sorted(settings.paths.docs.glob("*.json")):
        if path.name != "load_report.json":
            d = Document.model_validate_json(path.read_text(encoding="utf-8"))
            docs[d.source_id] = d
    facts = [Fact(**f) for f in json.loads((settings.paths.facts / "facts.json").read_text(encoding="utf-8"))]

    raw = fact_cards(facts, docs)
    for sid in titles:  # registry order
        if sid in docs:
            raw += doc_chunks(docs[sid])
    chunks, dup = dedupe(raw)

    max_chars = settings.chunking.max_chars
    records = []
    for c in chunks:
        d = docs[c["source_id"]]
        Chunk(**{k: c.get(k) for k in Chunk.model_fields if k in c})  # validate against the contract
        assert 0 < len(c["text"]) <= max_chars + 300, (c["chunk_id"], len(c["text"]))
        records.append({**c, "title": d.title, "url": d.url, "publisher": d.publisher.value,
                        "doc_type": d.doc_type.value, "doc_date": d.doc_date.isoformat() if d.doc_date else None,
                        "fetched_at": d.fetched_at.isoformat(), "chars": len(c["text"])})

    settings.paths.chunks.mkdir(parents=True, exist_ok=True)
    out = settings.paths.chunks / "chunks.json"
    out.write_text(json.dumps(records, indent=1, ensure_ascii=False), encoding="utf-8")

    by_src = Counter(r["source_id"] for r in records)
    by_kind = Counter(r["kind"] for r in records)
    sizes = [r["chars"] for r in records if r["kind"] != "fact_card"]
    report = {"total": len(records), "by_kind": by_kind, "by_source": by_src, "duplicates_removed": dup,
              "avg_chars": sum(sizes) // max(len(sizes), 1), "max_chars": max(sizes or [0]),
              "fact_cards_per_scheme": Counter(r["scheme_id"] for r in records if r["kind"] == "fact_card")}
    (settings.paths.chunks / "chunk_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for sid, n in by_src.items():
        print(f"[chunk] {sid:<26} {n:>4}")
    print(f"[chunk] total {len(records)} {dict(by_kind)}; duplicates removed {dup}; "
          f"avg {report['avg_chars']} chars, max {report['max_chars']} -> {out}")
    return records


def main() -> None:
    run()


if __name__ == "__main__":
    main()
