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


def detect_scheme(text: str) -> str | None:
    """Return the scheme_id named in `text` (longest matching alias wins)."""
    t = " " + re.sub(r"[^a-z0-9\- ]", " ", text.lower()) + " "
    best, best_len = None, 0
    for sid, scheme in SCHEMES.items():
        for alias in scheme.aliases:
            if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", t) and len(alias) > best_len:
                best, best_len = sid, len(alias)
    return best
