"""Step 5 - Verifier: an answer is returned only if every rule passes.

V1 citation exists   the cited chunk_id is one of the chunks actually retrieved
V2 URL verified      the cited URL belongs to an active/manual source in sources.yaml
V3 numbers grounded  every number in the answer appears in the evidence text (after normalisation)
V4 length            at most `answer.max_sentences` sentences
V5 policy            the answer itself contains no advice / return-claim wording
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from fundfacts.config import settings
from fundfacts.query.guardrails import ADVICE, RETURNS
from fundfacts.schemas import SourceStatus
from fundfacts.sources import load_sources

WORD_NUMBERS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
                "eight": "8", "nine": "9", "ten": "10", "twelve": "12", "fifteen": "15", "thirty": "30"}
# Advice phrased as a statement by the assistant (the question-side ADVICE pattern targets user wording)
DIRECTIVE = re.compile(r"\b(you\s+(should|must|could|may\s+want\s+to|ought\s+to)|i\s+(recommend|suggest|advise)|"
                       r"(good|great|better|best|ideal)\s+(choice|option|investment|fund)|consider\s+(investing|buying))\b", re.I)
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])")
ABBREV = re.compile(r"\b(Rs|No|Mr|Ms|Dr|p\.a|i\.e|e\.g|viz|etc|vs|Ltd|Co|incl|excl|approx)\.$", re.I)


@lru_cache(maxsize=1)
def allowed_urls() -> set[str]:
    return {str(s.url) for s in load_sources() if s.status in (SourceStatus.ACTIVE, SourceStatus.MANUAL)}


def numbers(text: str) -> set[float]:
    t = text.lower()
    for w, d in WORD_NUMBERS.items():
        t = re.sub(rf"\b{w}\b", d, t)
    out = set()
    for n in NUM.findall(t):
        try:
            out.add(float(n.replace(",", "")))
        except ValueError:
            pass
    return out


def sentences(text: str) -> list[str]:
    parts, buf = [], ""
    for piece in SENTENCE_END.split(text.strip()):
        buf = f"{buf} {piece}".strip() if buf else piece
        if not ABBREV.search(buf):
            parts.append(buf)
            buf = ""
    if buf:
        parts.append(buf)
    return [p for p in parts if p]


def trim_sentences(text: str, n: int | None = None) -> str:
    n = n or settings.answer.max_sentences
    return " ".join(sentences(re.sub(r"https?://\S+", "", text))[:n]).strip()


@dataclass
class Check:
    ok: bool
    failures: list[str] = field(default_factory=list)


def verify(answer: str, cited_chunk_id: str, cited_url: str, retrieved_ids: set[str], evidence_text: str,
           extra_allowed_numbers: set[float] | None = None) -> Check:
    fails = []
    if cited_chunk_id not in retrieved_ids:
        fails.append("V1: cited chunk was not retrieved")
    if cited_url not in allowed_urls():
        fails.append("V2: cited URL is not in the source registry")
    ungrounded = numbers(answer) - numbers(evidence_text) - (extra_allowed_numbers or set())
    if ungrounded:
        fails.append(f"V3: numbers not in the source: {sorted(ungrounded)[:5]}")
    if len(sentences(answer)) > settings.answer.max_sentences:
        fails.append("V4: more than the allowed number of sentences")
    policy_text = re.sub(r"Total Returns? Index|\(TRI\)", "", answer, flags=re.I)  # index names are not return claims
    policy_text = re.sub(r"\btax\w*\b.*", "", policy_text, flags=re.I)
    if ADVICE.search(answer) or RETURNS.search(policy_text) or DIRECTIVE.search(answer):
        fails.append("V5: answer contains advice or performance wording")
    return Check(ok=not fails, failures=fails)
