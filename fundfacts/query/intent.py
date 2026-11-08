"""Step 2 - Intent: which scheme and which fact field is the question about?

Deterministic keyword rules (no LLM), so routing is explainable and testable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from fundfacts.schemas import FactField
from fundfacts.schemes import detect_scheme

# Ordered: the first matching rule wins for the primary field.
FIELD_RULES: list[tuple[FactField, re.Pattern]] = [
    (FactField.MIN_SIP, re.compile(r"\b(min(imum)?\.?\s+sip|sip\s+(amount|minimum|instal+ment)|start\s+(an?\s+)?sip|"
                                   r"sip\s+(of|with|for)\s+(how\s+much|what)|how\s+much.{0,25}\bsip|lowest\s+sip)\b", re.I)),
    (FactField.MIN_LUMPSUM, re.compile(r"\b(min(imum)?\.?\s+(investment|amount|application|lump\s*sum|purchase)|"
                                       r"lump\s*sum|minimum\s+to\s+invest|how\s+much.{0,20}\b(invest|start))\b", re.I)),
    (FactField.EXPENSE_RATIO, re.compile(r"\b(expense\s+ratio|ter\b|total\s+expense|expenses?\s+charged|fund\s+expenses?)", re.I)),
    (FactField.EXIT_LOAD, re.compile(r"\b(exit\s+load|exit\s+charges?|redemption\s+(charge|fee|load)|load\s+on\s+(exit|redemption)|"
                                     r"charge\s+(for|on)\s+(early\s+)?(redeem|redemption|withdraw))", re.I)),
    (FactField.LOCK_IN, re.compile(r"\b(lock[\s-]?in|locked|lockin)\b", re.I)),
    (FactField.RISKOMETER, re.compile(r"\b(riskometer|risk[\s-]?o[\s-]?meter|risk\s+level|risk\s+category|how\s+risky|risk\s+rating)\b", re.I)),
    (FactField.BENCHMARK, re.compile(r"\b(benchmark|index\s+(does\s+it\s+)?(track|follow))\b", re.I)),
    (FactField.FUND_MANAGER, re.compile(r"\b(fund\s+manager|managers?|who\s+manages|managed\s+by|who\s+runs)\b", re.I)),
    (FactField.OBJECTIVE, re.compile(r"\b(objective|aim|goal\s+of\s+the\s+(fund|scheme)|what\s+does\s+.{0,40}\s+invest\s+in)\b", re.I)),
    (FactField.CATEGORY, re.compile(r"\b(category|what\s+(type|kind)\s+of\s+(fund|scheme)|type\s+of\s+(fund|scheme))\b", re.I)),
]

OTHER_AMCS = re.compile(
    r"\b(sbi|icici|axis|nippon|kotak|aditya\s+birla|uti|mirae|dsp|tata|franklin|quant|parag\s+parikh|ppfas|motilal|"
    r"canara|edelweiss|invesco|bandhan|sundaram|hsbc|baroda|lic\s+mf|groww\s+mutual)\b", re.I)
OTHER_HDFC = re.compile(r"\bHDFC\s+([A-Za-z0-9&\-]+(?:\s+[A-Za-z0-9&\-]+){0,5}?)\s+(Fund|FOF|ETF)\b", re.I)
PLAN_WORDS = re.compile(r"\b(direct|regular|growth|idcw|plan|option)\b", re.I)


@dataclass
class Intent:
    scheme_id: str | None
    fields: list[FactField] = field(default_factory=list)
    out_of_scope: str | None = None  # e.g. "HDFC Balanced Advantage Fund" or "SBI"

    @property
    def field(self) -> FactField | None:
        return self.fields[0] if self.fields else None


def detect_fields(query: str) -> list[FactField]:
    found = []
    for f, pat in FIELD_RULES:
        if pat.search(query) and f not in found:
            found.append(f)
    # "minimum SIP" also matches the generic minimum rule - keep only the specific one
    if FactField.MIN_SIP in found and FactField.MIN_LUMPSUM in found:
        found.remove(FactField.MIN_LUMPSUM)
    return found


def detect(query: str) -> Intent:
    from fundfacts.schemes import DOC_NAME_PATTERNS

    fields = detect_fields(query)
    # A full HDFC scheme name decides first: "HDFC Large & Mid Cap Fund" must not be read as "Mid Cap".
    for m in OTHER_HDFC.finditer(query):
        name = f"HDFC {m.group(1).strip()} {m.group(2)}"
        bare = re.sub(r"\s+", " ", PLAN_WORDS.sub(" ", name)).strip()  # "HDFC Large Cap Direct Plan Fund" -> "HDFC Large Cap Fund"
        ours = [sid for sid, pat in DOC_NAME_PATTERNS.items() if pat.match(name) or pat.match(bare)]  # anchored at "HDFC"
        if ours:
            return Intent(scheme_id=ours[0], fields=fields)
        if not re.fullmatch(r"(mutual|mf)", m.group(1).strip(), re.I):
            return Intent(scheme_id=None, fields=fields, out_of_scope=name)
    if OTHER_AMCS.search(query):
        return Intent(scheme_id=None, fields=fields, out_of_scope=OTHER_AMCS.search(query).group(0))
    return Intent(scheme_id=detect_scheme(query), fields=fields)
