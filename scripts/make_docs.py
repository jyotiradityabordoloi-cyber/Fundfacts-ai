"""Generate the submission deliverables from the real pipeline outputs.

    python scripts/make_docs.py

Writes
    SOURCES.md     source list with publisher, type, scheme, status and retrieval date
    sources.csv    the same list as CSV
    SAMPLE_QA.md   real answers produced by the assistant (incl. refusals) with links and dates
"""
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from fundfacts.config import settings  # noqa: E402
from fundfacts.query.answer import answer  # noqa: E402
from fundfacts.schemes import SCHEMES  # noqa: E402
from fundfacts.sources import load_sources  # noqa: E402

IST = timezone(timedelta(minutes=330))
SAMPLE_QUESTIONS = [
    "What is the expense ratio of HDFC Balanced Advantage Fund?",
    "What is the lock-in period of HDFC ELSS Tax Saver?",
    "What is the exit load of HDFC Small Cap Fund?",
    "What is the minimum SIP amount for HDFC Small Cap Fund?",
    "What is the riskometer level of HDFC Flexi Cap Fund?",
    "What is the benchmark of HDFC Large Cap Fund?",
    "What is a consolidated account statement?",
    "Should I buy HDFC Balanced Advantage Fund now?",
    "What were the 3-year returns of HDFC Flexi Cap Fund?",
    "My PAN is ABCDE1234F, can you check my holdings?",
    "Minimum SIP for HDFC Balanced Advantage Fund?",
]


INVENTORY_IDS = [f"SRC-{i:03d}" for i in range(1, 25)]
STATE = {"active": "ingested", "manual": "manual download pending", "blocked": "not ingested - blocked",
         "excluded": "not ingested - excluded", "historical": "not ingested - historical"}


def first_sentence(text: str) -> str:
    text = " ".join(text.split())
    return text.split(". ")[0].rstrip(".") + "." if text else ""


def sources_docs() -> int:
    manifest = {m["source_id"]: m for m in json.loads((settings.paths.raw / "manifest.json").read_text(encoding="utf-8"))}
    sources = load_sources()
    rows = []
    for s in sources:
        m = manifest.get(s.source_id, {})
        fetched = m.get("fetched_at") if m.get("path") else None
        state = STATE[s.status.value]
        if s.status.value == "manual" and fetched:
            state = "ingested (manual download)"
        if s.status.value == "active" and not fetched:
            state = "fetch failed"
        rows.append({
            "source_id": s.source_id, "publisher": s.publisher.value, "doc_type": s.doc_type.value, "title": s.title,
            "scheme": SCHEMES[s.scheme_id].name if s.scheme_id else "", "status": state,
            "inventory_ref": s.inventory_ref or "", "replaces": " ".join(s.replaces), "checked_on": s.checked_on or "",
            "retrieved": datetime.fromisoformat(fetched).astimezone(IST).strftime("%d %b %Y") if fetched else "",
            "url": str(s.url), "notes": " ".join(s.notes.split()),
        })
    with open(ROOT / "sources.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    corpus = [r for r in rows if r["status"].startswith(("ingested", "manual", "fetch"))]
    ingested = [r for r in rows if r["status"].startswith("ingested")]
    reviewed = [r for r in rows if r["status"].startswith("not ingested")]
    lines = ["# Sources", "",
             "FundFacts AI uses only official public sources from **HDFC Mutual Fund (AMC), SEBI and AMFI**. "
             f"The corpus has **{len(corpus)} registered sources** ({len(ingested)} ingested, "
             f"{len(corpus) - len(ingested)} awaiting a manual download). Each URL is fetched exactly once per build "
             "and links inside pages are never followed. The registry is [`sources.yaml`](sources.yaml) and the "
             "machine-readable list is [`sources.csv`](sources.csv); this page is generated from them by "
             "`python scripts/make_docs.py`.", "",
             "## Corpus", "",
             "| # | Publisher | Type | Title | Scheme | Inventory | Status | Retrieved (IST) |",
             "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(corpus, 1):
        inv = r["inventory_ref"] or (f"replaces {r['replaces'].replace(' ', ', ')}" if r["replaces"] else "added")
        lines.append(f"| {i} | {r['publisher']} | {r['doc_type']} | [{r['title']}]({r['url']}) | {r['scheme'] or '-'} | "
                     f"{inv} | {r['status']} | {r['retrieved'] or '-'} |")
    lines += ["", "## Reviewed, not ingested", "",
              "| Inventory | Publisher | Title | Decision | Reason | Re-checked |", "|---|---|---|---|---|---|"]
    for r in reviewed:
        lines.append(f"| {r['inventory_ref'] or '-'} | {r['publisher']} | [{r['title']}]({r['url']}) | "
                     f"{r['status'].replace('not ingested - ', '')} | {first_sentence(r['notes'])} | {r['checked_on'] or '-'} |")

    # ---- reconciliation against the original 24-entry inventory
    by_ref = {s.inventory_ref: s for s in sources if s.inventory_ref}
    lines += ["", "## Inventory reconciliation (SRC-001 ... SRC-024)", "",
              "Every candidate from the original source inventory and what happened to it.", "",
              "| Inventory | Candidate | Decision | In the corpus as |", "|---|---|---|---|"]
    counts = {"ingested": 0, "replaced": 0, "excluded": 0, "historical": 0}
    for ref in INVENTORY_IDS:
        s = by_ref.get(ref)
        stand_ins = [x.source_id for x in sources if ref in x.replaces]
        if s is None:
            lines.append(f"| {ref} | - | **UNACCOUNTED** | - |")
            continue
        if s.status.value in ("active", "manual"):
            decision, used = "ingested", f"`{s.source_id}`"
            counts["ingested"] += 1
        elif s.status.value == "blocked":
            decision, used = "blocked (HTTP 403) - replaced", ", ".join(f"`{x}`" for x in stand_ins) or "-"
            counts["replaced"] += 1
        elif s.status.value == "historical":
            decision, used = "historical - excluded", "-"
            counts["historical"] += 1
        else:
            decision, used = "excluded", "-"
            counts["excluded"] += 1
        lines.append(f"| {ref} | [{s.title}]({s.url}) | {decision} | {used} |")
    added = [r for r in corpus if not r["inventory_ref"] and not r["replaces"]]
    lines += ["", f"Of the 24 inventory entries: **{counts['ingested']} ingested**, **{counts['replaced']} replaced** by the same "
              f"official documents on `files.hdfcfund.com`, **{counts['excluded']} excluded** after review and "
              f"**{counts['historical']} historical**. {len(added)} official sources were added beyond the inventory: "
              + ", ".join(f"`{r['source_id']}`" for r in added) + ".",
              "", "## Notes",
              "- `www.hdfcfund.com` returns HTTP 403 to automated requests. HDFC's own document server `files.hdfcfund.com` "
              "does not, so scheme facts come from the official SIDs, the Common Equity KIM and the monthly factsheet there.",
              "- Pages from `www.hdfcfund.com` marked *manual* are saved by hand into `data/manual/`; their original URL stays the citation.",
              "- Returns, SIP-performance, risk-ratio and portfolio sections are removed from documents before anything is stored.",
              ""]
    (ROOT / "SOURCES.md").write_text("\n".join(lines), encoding="utf-8")
    return len(ingested)


def sample_qa() -> int:
    who = {"gemini": "Gemini", "anthropic": "Claude"}.get(settings.llm.active or "")
    mode = f"{who} + verifier" if who else "no LLM key: exact facts + verified extractive answers"
    lines = ["# Sample Q&A", "",
             f"Generated by `python scripts/make_docs.py` on {datetime.now(IST):%d %b %Y} from the real pipeline "
             f"({mode}). Each answer has one source link and the date the source was retrieved.", ""]
    for i, q in enumerate(SAMPLE_QUESTIONS, 1):
        a = answer(q)
        lines += [f"### {i}. {q}", "", f"> {a.text}", "",
                  f"- **Type:** `{a.type.value}` (path: `{a.path}`)",
                  f"- **{'Source' if a.type.value == 'answer' else 'Official link'}:** [{a.source_title}]({a.source_url})"]
        if a.last_updated:
            lines.append(f"- **Last updated from sources:** {a.last_updated}")
        lines.append("")
    (ROOT / "SAMPLE_QA.md").write_text("\n".join(lines), encoding="utf-8")
    return len(SAMPLE_QUESTIONS)


if __name__ == "__main__":
    n_src = sources_docs()
    n_qa = sample_qa()
    print(f"SOURCES.md + sources.csv: {n_src} ingested sources; SAMPLE_QA.md: {n_qa} questions")
