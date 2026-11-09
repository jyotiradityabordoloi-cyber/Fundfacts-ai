"""Scheme fact sheets for the "Explore schemes" panel - straight from data/facts/facts.json.

Every value shown is an extracted, quoted fact with its source document, page and as-on date;
fields that were not found are listed as missing (never filled in).
"""
from __future__ import annotations

from functools import lru_cache

from fundfacts.query.answer import FIELD_NAMES, _ist, _source_meta
from fundfacts.query.fact_lookup import clean_value, get_fact
from fundfacts.schemas import FactField
from fundfacts.schemes import SCHEMES

ORDER = [FactField.CATEGORY, FactField.EXPENSE_RATIO, FactField.EXIT_LOAD, FactField.MIN_SIP, FactField.MIN_LUMPSUM,
         FactField.LOCK_IN, FactField.RISKOMETER, FactField.BENCHMARK, FactField.FUND_MANAGER, FactField.OBJECTIVE]
LABELS = {
    FactField.CATEGORY: "Category", FactField.EXPENSE_RATIO: "Expense ratio", FactField.EXIT_LOAD: "Exit load",
    FactField.MIN_SIP: "Minimum SIP", FactField.MIN_LUMPSUM: "Minimum lumpsum", FactField.LOCK_IN: "Lock-in",
    FactField.RISKOMETER: "Riskometer", FactField.BENCHMARK: "Benchmark", FactField.FUND_MANAGER: "Fund manager(s)",
    FactField.OBJECTIVE: "Objective",
}
QUESTIONS = {
    FactField.EXPENSE_RATIO: "What is the expense ratio of {name}?",
    FactField.EXIT_LOAD: "What is the exit load of {name}?",
    FactField.MIN_SIP: "What is the minimum SIP for {name}?",
    FactField.LOCK_IN: "Does {name} have a lock-in period?",
    FactField.RISKOMETER: "What is the riskometer level of {name}?",
    FactField.BENCHMARK: "What is the benchmark of {name}?",
    FactField.FUND_MANAGER: "Who manages {name}?",
}


@lru_cache(maxsize=1)
def scheme_cards() -> list[dict]:
    meta = _source_meta()
    cards = []
    for sid, scheme in SCHEMES.items():
        facts, missing = [], []
        for field in ORDER:
            f = get_fact(sid, field)
            if not f:
                missing.append(LABELS[field])
                continue
            src = meta.get(f.source_id, {})
            facts.append({
                "field": field.value, "label": LABELS[field], "value": clean_value(f.value),
                "as_of": f.as_of.strftime("%d %b %Y") if f.as_of else None,
                "source_title": f"{src.get('title', f.source_id)}, page {f.page}",
                "source_url": src.get("url"), "retrieved": _ist(src.get("fetched_at")),
            })
        cards.append({
            "scheme_id": sid, "name": scheme.name, "category": scheme.category, "plan": "Direct Plan - Growth",
            "facts": facts, "missing": missing,
            "questions": [q.format(name=scheme.name) for q in QUESTIONS.values()],
        })
    return cards


__all__ = ["scheme_cards", "FIELD_NAMES"]
