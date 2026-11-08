"""The five schemes in scope and their aliases (used by intent detection)."""
from __future__ import annotations

import re

from pydantic import BaseModel


class Scheme(BaseModel):
    scheme_id: str
    name: str
    category: str
    aliases: list[str]


SCHEMES: dict[str, Scheme] = {s.scheme_id: s for s in [
    Scheme(scheme_id="hdfc_large_cap", name="HDFC Large Cap Fund", category="Large Cap",
           aliases=["hdfc large cap", "large cap", "largecap", "large-cap", "hdfc top 100", "top 100"]),
    Scheme(scheme_id="hdfc_flexi_cap", name="HDFC Flexi Cap Fund", category="Flexi Cap",
           aliases=["hdfc flexi cap", "flexi cap", "flexicap", "flexi-cap", "hdfc equity fund"]),
    Scheme(scheme_id="hdfc_elss", name="HDFC ELSS Tax Saver Fund", category="ELSS",
           aliases=["hdfc elss", "elss", "tax saver", "taxsaver", "tax-saver", "tax saving fund", "hdfc taxsaver"]),
    Scheme(scheme_id="hdfc_mid_cap", name="HDFC Mid Cap Fund", category="Mid Cap",
           aliases=["hdfc mid cap", "mid cap", "midcap", "mid-cap", "mid cap opportunities", "mid-cap opportunities"]),
    Scheme(scheme_id="hdfc_small_cap", name="HDFC Small Cap Fund", category="Small Cap",
           aliases=["hdfc small cap", "small cap", "smallcap", "small-cap"]),
]}

PLAN_LABEL = "Direct Plan - Growth Option"

# Scheme names as printed in HDFC documents (incl. former names). Used by ingestion to tag pages
# and by intent detection to recognise full scheme names - kept here so the serverless runtime
# needs no PDF libraries.
DOC_NAME_PATTERNS: dict[str, re.Pattern] = {
    "hdfc_large_cap": re.compile(r"HDFC\s+Large\s+Cap\s+Fund|HDFC\s+Top\s+100", re.I),
    "hdfc_flexi_cap": re.compile(r"HDFC\s+Flexi\s+Cap\s+Fund|HDFC\s+Equity\s+Fund", re.I),
    "hdfc_elss": re.compile(r"HDFC\s+ELSS\s*-?\s*T\s?ax\s*saver|HDFC\s+TaxSaver", re.I),  # PDFs sometimes print "T ax"
    "hdfc_mid_cap": re.compile(r"HDFC\s+Mid[\s-]*Cap\s+(Opportunities\s+)?Fund", re.I),
    "hdfc_small_cap": re.compile(r"HDFC\s+Small\s+Cap\s+Fund", re.I),
}


def detect_scheme(text: str) -> str | None:
    """Return the scheme_id named in `text` (longest matching alias wins)."""
    t = " " + re.sub(r"[^a-z0-9\- ]", " ", text.lower()) + " "
    best, best_len = None, 0
    for sid, scheme in SCHEMES.items():
        for alias in scheme.aliases:
            if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", t) and len(alias) > best_len:
                best, best_len = sid, len(alias)
    return best
