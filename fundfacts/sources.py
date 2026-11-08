"""Source registry: load and validate sources.yaml.

    python -m fundfacts.sources            # summary of the registry
    python -m fundfacts.sources --check    # also check each URL / manual file (nothing is saved)
"""
from __future__ import annotations

import sys
from collections import Counter

import yaml

from fundfacts.config import settings
from fundfacts.schemas import Source, SourceStatus
from fundfacts.schemes import SCHEMES

MIN_CORPUS, MAX_CORPUS = 15, 25
INGESTED = {SourceStatus.ACTIVE, SourceStatus.MANUAL}


def load_sources() -> list[Source]:
    raw = yaml.safe_load(settings.paths.sources.read_text(encoding="utf-8"))
    sources = [Source(**s) for s in raw["sources"]]
    ids = [s.source_id for s in sources]
    dupes = [i for i, n in Counter(ids).items() if n > 1]
    if dupes:
        raise ValueError(f"duplicate source_id(s): {dupes}")
    bad = [s.source_id for s in sources if s.scheme_id and s.scheme_id not in SCHEMES]
    if bad:
        raise ValueError(f"unknown scheme_id in: {bad}")
    return sources


def corpus(sources: list[Source] | None = None) -> list[Source]:
    """Sources that are ingested (active + manual)."""
    return [s for s in (sources or load_sources()) if s.status in INGESTED]


def manual_file(source: Source):
    matches = sorted(settings.paths.manual.glob(f"{source.source_id}.*"))
    return matches[0] if matches else None


def check(sources: list[Source]) -> int:
    import requests

    headers = {"User-Agent": settings.scrape.user_agent}
    problems = 0
    for s in sources:
        if s.status == SourceStatus.MANUAL:
            f = manual_file(s)
            state = f"manual file {'present: ' + f.name if f else 'MISSING (data/manual/' + s.source_id + '.html)'}"
            problems += f is None
        elif s.status == SourceStatus.ACTIVE:
            try:
                r = requests.get(str(s.url), headers=headers, timeout=settings.scrape.timeout_s, stream=True)
                head = next(r.iter_content(8), b"")
                r.close()
                kind = "pdf" if head.startswith(b"%PDF") else (r.headers.get("content-type", "").split(";")[0] or "?")
                state = f"HTTP {r.status_code} {kind}"
                problems += r.status_code != 200
            except Exception as exc:  # noqa: BLE001
                state = f"ERROR {type(exc).__name__}"
                problems += 1
        else:
            state = s.status.value
        print(f"  {s.source_id:<26} {s.publisher.value:<5} {s.doc_type.value:<9} {state}")
    return problems


def main(argv: list[str]) -> None:
    sources = load_sources()
    ingested = corpus(sources)
    by_status = Counter(s.status.value for s in sources)
    by_pub = Counter(s.publisher.value for s in ingested)
    print(f"registry: {len(sources)} entries {dict(by_status)}")
    print(f"corpus:   {len(ingested)} sources {dict(by_pub)}  (target {MIN_CORPUS}-{MAX_CORPUS})")
    for sid in SCHEMES:
        docs = [s.source_id for s in ingested if s.scheme_id == sid]
        print(f"  {sid:<16} scheme-specific: {', '.join(docs) or 'NONE'}")
    if not MIN_CORPUS <= len(ingested) <= MAX_CORPUS:
        print("WARNING: corpus size outside the 15-25 target")
    if "--check" in argv:
        print("checking sources (nothing is saved):")
        problems = check(sources)
        print(f"{problems} problem(s)")
        sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
