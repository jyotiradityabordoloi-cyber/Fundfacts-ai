"""Step 3a - Exact fact lookup: answer from data/facts/facts.json with a template (no LLM)."""
from __future__ import annotations

import json
import re
from functools import lru_cache

from fundfacts.config import settings
from fundfacts.schemas import Fact, FactField
from fundfacts.schemes import SCHEMES
from fundfacts.sources import load_sources

TEMPLATES = {
    FactField.EXPENSE_RATIO: "The expense ratio of {scheme}{as_of} is {value}.",
    FactField.EXIT_LOAD: "Exit load for {scheme}: {value}",
    FactField.MIN_SIP: "{scheme} - {value} (DSIP/WSIP/MSIP/QSIP/HSIP/YSIP = daily, weekly, monthly, quarterly, "
                       "half-yearly and yearly SIP).",
    FactField.MIN_LUMPSUM: "The minimum application (lumpsum) amount for {scheme} is {value}.",
    FactField.LOCK_IN: "{scheme}: {value}.",
    FactField.RISKOMETER: "The riskometer level of {scheme}{as_of} is {value}.",
    FactField.BENCHMARK: "The benchmark of {scheme} is {value}.",
    FactField.FUND_MANAGER: "{scheme}{as_of} is managed by {value}.",
    FactField.CATEGORY: "{scheme} belongs to the SEBI category \"{value}\".",
    FactField.OBJECTIVE: "The investment objective of {scheme} is: {value}",
}
ELSS_LOCK_IN = "{scheme} has a lock-in period of {value}."


@lru_cache(maxsize=1)
def _facts() -> dict[tuple[str, FactField], Fact]:
    path = settings.paths.facts / "facts.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    return {(f["scheme_id"], FactField(f["field"])): Fact(**f) for f in data}


@lru_cache(maxsize=1)
def _sources() -> dict:
    return {s.source_id: s for s in load_sources()}


def get_fact(scheme_id: str, field: FactField) -> Fact | None:
    f = _facts().get((scheme_id, field))
    return f if f and f.status == "found" else None


def source_of(fact: Fact):
    return _sources()[fact.source_id]


def clean_value(value: str) -> str:
    """Remove PDF bullet dashes at sentence starts ("... allotment. - No Exit Load ...")."""
    return re.sub(r"(^|(?<=\.))\s*'?[-–]\s+(?=[A-Z])", " ", value).strip().rstrip(".")


def render(fact: Fact) -> str:
    scheme = SCHEMES[fact.scheme_id].name
    as_of = f" (as on {fact.as_of.strftime('%d %b %Y')})" if fact.as_of and fact.field in (
        FactField.EXPENSE_RATIO, FactField.RISKOMETER, FactField.FUND_MANAGER) else ""
    tpl = ELSS_LOCK_IN if fact.field == FactField.LOCK_IN and fact.scheme_id == "hdfc_elss" else TEMPLATES[fact.field]
    value = clean_value(fact.value)
    text = tpl.format(scheme=scheme, value=value, as_of=as_of)
    return text if text.endswith((".", "?", "!")) else text + "."
