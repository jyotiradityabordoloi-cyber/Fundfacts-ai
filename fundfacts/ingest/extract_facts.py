"""Phase 4 - Extract facts: a structured, quoted fact table for the five schemes.

    python -m fundfacts.ingest.extract_facts

Each field has an ordered list of extractors (most authoritative/current source first).
An extractor returns a Fact with the value, the page it came from and a verbatim quote,
or None. If every extractor returns None the field is recorded as `missing`.
Values are NEVER filled from defaults or from another scheme.

Output
    data/facts/facts.json        list[Fact]
    (coverage table printed: scheme x field -> found/missing + source)
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from functools import lru_cache
from typing import Callable

from fundfacts.config import settings
from fundfacts.ingest.load import parse_date
from fundfacts.schemes import DOC_NAME_PATTERNS
from fundfacts.schemas import Document, Fact, FactField
from fundfacts.schemes import SCHEMES

FACTSHEET = "hdfc_factsheet_sep_2026"
KIM = "hdfc_common_equity_kim"


# ------------------------------------------------------------------ helpers
@lru_cache(maxsize=None)
def doc(source_id: str) -> Document | None:
    path = settings.paths.docs / f"{source_id}.json"
    return Document.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def tidy(value: str) -> str:
    """Fix PDF spacing artefacts ('switch -in', 'Rs.100/-', '• ') without changing meaning."""
    v = flat(value)
    v = re.sub(r"\s*•\s*", " ", v)
    v = re.sub(r"(\w) -(\w)", r"\1-\2", v)
    v = re.sub(r"/\s*-", "/-", v)
    return v.strip(" -;")


def fact(scheme_id: str, field: FactField, value: str, src: Document, page: int, quote: str,
         as_of: date | None = None) -> Fact:
    return Fact(scheme_id=scheme_id, field=field, status="found", value=tidy(value),
                as_of=as_of or src.doc_date, source_id=src.source_id, page=page, quote=flat(quote)[:400])


def sid_doc(scheme_id: str) -> Document | None:
    return doc(f"{scheme_id}_sid")


def section(text: str, start: str, end: str) -> re.Match | None:
    """Text between a start label and the next end label (DOTALL, case-insensitive)."""
    return re.search(rf"({start})(.*?)(?={end})", text, re.S | re.I)


def factsheet_page(scheme_id: str):
    """The factsheet page that *belongs* to the scheme (header ownership from Phase 3)."""
    fs = doc(FACTSHEET)
    if not fs:
        return None, None
    for p in fs.pages:
        if p.scheme_ids == [scheme_id] and "EXPENSE RATIO" in p.text:
            return fs, p
    return fs, None


# ------------------------------------------------------------------ extractors
def expense_ratio_factsheet(sid: str) -> Fact | None:
    fs, p = factsheet_page(sid)
    if not p:
        return None
    m = re.search(r"EXPENSE RATIO\s*\(As On ([^)]+)\).*?Regular:\s*([\d.]+%)\s*Direct:\s*([\d.]+%)", p.text, re.S | re.I)
    if not m:
        return None
    value = f"Direct Plan {m.group(3)}; Regular Plan {m.group(2)} (base expense ratio incl. statutory levies, " \
            f"excl. brokerage and transaction costs)"
    return fact(sid, FactField.EXPENSE_RATIO, value, fs, p.n, f"Regular: {m.group(2)} Direct: {m.group(3)}",
                as_of=parse_date(m.group(1)))


def exit_load_sid(sid: str) -> Fact | None:
    d = sid_doc(sid)
    for p in d.pages if d else []:
        m = section(p.text, r"Load Structure\s*Exit Load\s*:", r"In respect of Systematic|XII\.|Minimum Application")
        if m and m.group(2).strip():
            return fact(sid, FactField.EXIT_LOAD, m.group(2), d, p.n, m.group(0))
    return None


def exit_load_factsheet(sid: str) -> Fact | None:
    fs, p = factsheet_page(sid)
    m = p and section(p.text, r"EXIT LOAD\$*", r"\.\.\.\.Contd|LOCK-IN|$")
    return fact(sid, FactField.EXIT_LOAD, m.group(2), fs, p.n, m.group(0)) if m else None


def min_lumpsum_sid(sid: str) -> Fact | None:
    d = sid_doc(sid)
    for p in d.pages if d else []:
        m = section(p.text, r"XII\.\s*Minimum Application\s*Amount\s*/\s*Switch In", r"XIII\.")
        if m:
            return fact(sid, FactField.MIN_LUMPSUM, m.group(2), d, p.n, m.group(0))
    return None


def min_sip_ssd(sid: str) -> Fact | None:
    d = doc(f"{sid}_ssd")
    for p in d.pages if d else []:
        m = re.search(r"Minimum\s+amount\s*For SIP\s*(.*?)(?=\.\s*For SWAP|For SWAP)", p.text, re.S | re.I)
        if m:
            return fact(sid, FactField.MIN_SIP, f"SIP minimum per instalment: {m.group(1)}", d, p.n, m.group(0))
    return None


def lock_in_factsheet(sid: str) -> Fact | None:
    fs, p = factsheet_page(sid)
    m = p and re.search(r"LOCK-IN PERIOD\s*(.*?)(?=EXIT LOAD|\.\.\.\.Contd|$)", p.text, re.S)
    return fact(sid, FactField.LOCK_IN, m.group(1), fs, p.n, m.group(0)) if m else None


def lock_in_sid(sid: str) -> Fact | None:
    d = sid_doc(sid)
    for p in (d.pages[:6] if d else []):
        m = re.search(r"statutory\s+lock\s*-?\s*in\s+of\s+(\d+\s+years?)", p.text, re.I | re.S)
        if m:
            return fact(sid, FactField.LOCK_IN, f"{m.group(1)} (statutory lock-in for ELSS)", d, p.n, m.group(0))
    return None


def no_lock_in_sid(sid: str) -> Fact | None:
    """Non-ELSS: the SID's liquidity clause says units are redeemable on any business day."""
    if sid == "hdfc_elss":
        return None
    d = sid_doc(sid)
    for p in (d.pages[:6] if d else []):
        m = re.search(r"Units of the [Ss]cheme can be redeemed\s*/\s*switched\s*out on any\s*Business day at NAV based prices", p.text, re.S)
        if m:
            return fact(sid, FactField.LOCK_IN, "No lock-in period; units can be redeemed or switched out on any "
                        "business day at NAV-based prices", d, p.n, m.group(0))
    return None


def riskometer_ssd(sid: str) -> Fact | None:
    d = doc(f"{sid}_ssd")
    for p in d.pages if d else []:
        m = re.search(r"Riskometer \(as on Date\)\s*([A-Za-z ]+? Risk)", p.text)
        if m:
            return fact(sid, FactField.RISKOMETER, m.group(1), d, p.n, m.group(0))
    return None


def riskometer_kim(sid: str) -> Fact | None:
    """KIM product-labelling pages list scheme names, then 'The risk of the Scheme is X' in the same
    order, then each scheme's benchmark in the same order. The match is accepted only when the
    benchmark at the same position equals the scheme's benchmark from its own SID."""
    kim, bench = doc(KIM), benchmark_sid(sid)
    if not kim or not bench:
        return None
    bench_key = re.sub(r"[^a-z0-9]", "", bench.value.lower())[:12]
    any_scheme = re.compile(r"(HDFC\s+[A-Z][\w&'\- ]*?(?:Fund|Saver|Plan))", re.S)
    for p in kim.pages:
        if "PRODUCT LABEL" not in p.text.upper() or not DOC_NAME_PATTERNS[sid].search(p.text):
            continue
        names = [n for n in any_scheme.findall(p.text.replace("\n", " ")) if "Formerly" not in n]
        names = list(dict.fromkeys(flat(n) for n in names))  # unique, in order
        risks = re.findall(r"The risk of the Scheme is ([A-Za-z ]+?)(?=\n|$)", p.text, re.M)
        benches = re.findall(r"([^\n]*\(TRI\)|[^\n]*Total Returns? Index[^\n]*)\n(?:\(as per AMFI Tier I Benchmark\)\n)?The risk of the Scheme", p.text)
        idx = next((i for i, n in enumerate(names) if DOC_NAME_PATTERNS[sid].search(n)), None)
        if idx is None or len(names) != len(risks) or len(benches) != len(risks):
            continue
        if re.sub(r"[^a-z0-9]", "", benches[idx].lower())[:12] != bench_key:
            continue
        return fact(sid, FactField.RISKOMETER, f"{risks[idx].strip()} Risk", kim, p.n,
                    f"{names[idx]} ... {benches[idx]} ... The risk of the Scheme is {risks[idx]}")
    return None


def benchmark_sid(sid: str) -> Fact | None:
    d = sid_doc(sid)
    for p in (d.pages[:8] if d else []):
        m = re.search(r"The benchmark of the scheme is\s*(.*?\))\s*\.", p.text, re.S | re.I)
        if m:
            return fact(sid, FactField.BENCHMARK, m.group(1), d, p.n, m.group(0))
    return None


def fund_manager_factsheet(sid: str) -> Fact | None:
    """Factsheet annexure 'Fund Manager / Funds Managed': invert manager -> schemes."""
    fs = doc(FACTSHEET)
    if not fs:
        return None
    found, page_no, quotes = [], None, []
    # "6. Mr . Bhagyesh Kagalkar (Fund Manager for Commodities related investments) HDFC ..." - role note is optional
    starter = re.compile(r"\d+\.\s*(?:Mr|Ms|Mrs)\s*\.?\s*([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\s*(\([^)]{3,80}\))?\s*(?=HDFC)")
    for p in fs.pages:
        if "Funds Managed" not in p.text:
            continue
        text = flat(p.text)
        starts = list(starter.finditer(text))
        for i, m in enumerate(starts):
            block = text[m.end(): starts[i + 1].start() if i + 1 < len(starts) else len(text)]
            if DOC_NAME_PATTERNS[sid].search(block):
                role = re.sub(r"^\(Fund Manager for\s*|\)$", "", m.group(2) or "").strip()
                name = flat(m.group(1)) + (f" ({role})" if role else "")
                if name not in found:
                    found.append(name)
                    quotes.append(f"{name}: {DOC_NAME_PATTERNS[sid].search(block).group(0)}")
                    page_no = page_no or p.n
    if not found:
        return None
    return fact(sid, FactField.FUND_MANAGER, ", ".join(found), fs, page_no, " | ".join(quotes))


def category_factsheet(sid: str) -> Fact | None:
    fs, p = factsheet_page(sid)
    m = p and re.search(r"CATEGORY OF SCHEME\s*\n([^\n]+)", p.text)
    return fact(sid, FactField.CATEGORY, m.group(1).title().replace("Elss", "ELSS"), fs, p.n, m.group(0)) if m else None


def objective_sid(sid: str) -> Fact | None:
    d = sid_doc(sid)
    for p in (d.pages[:8] if d else []):
        m = section(p.text, r"Investment Objective", r"There is no assurance|VI\.")
        if m and len(m.group(2).strip()) > 20:
            return fact(sid, FactField.OBJECTIVE, m.group(2), d, p.n, m.group(0))
    return None


# field -> extractors in priority order
EXTRACTORS: dict[FactField, list[Callable[[str], Fact | None]]] = {
    FactField.EXPENSE_RATIO: [expense_ratio_factsheet],
    FactField.EXIT_LOAD: [exit_load_sid, exit_load_factsheet],
    FactField.MIN_SIP: [min_sip_ssd],
    FactField.MIN_LUMPSUM: [min_lumpsum_sid],
    FactField.LOCK_IN: [lock_in_factsheet, lock_in_sid, no_lock_in_sid],
    FactField.RISKOMETER: [riskometer_ssd, riskometer_kim],
    FactField.BENCHMARK: [benchmark_sid],
    FactField.FUND_MANAGER: [fund_manager_factsheet],
    FactField.CATEGORY: [category_factsheet],
    FactField.OBJECTIVE: [objective_sid],
}


def extract(scheme_id: str, field: FactField) -> Fact:
    for fn in EXTRACTORS[field]:
        f = fn(scheme_id)
        if f and f.value:
            return f
    return Fact(scheme_id=scheme_id, field=field, status="missing")


def run() -> list[Fact]:
    facts = [extract(sid, field) for sid in SCHEMES for field in FactField]
    settings.paths.facts.mkdir(parents=True, exist_ok=True)
    out = settings.paths.facts / "facts.json"
    out.write_text(json.dumps([f.model_dump(mode="json") for f in facts], indent=1, ensure_ascii=False), encoding="utf-8")

    # coverage table
    fields = list(FactField)
    print(f"{'field':<15}" + "".join(f"{s.replace('hdfc_', ''):<12}" for s in SCHEMES))
    for field in fields:
        row = [next(f for f in facts if f.scheme_id == s and f.field == field) for s in SCHEMES]
        print(f"{field.value:<15}" + "".join(f"{('ok ' + (r.source_id or '').split('_')[-1]) if r.status == 'found' else 'MISSING':<12}" for r in row))
    found = sum(f.status == "found" for f in facts)
    print(f"[facts] {found}/{len(facts)} found -> {out}")
    return facts


def main() -> None:
    run()


if __name__ == "__main__":
    main()
