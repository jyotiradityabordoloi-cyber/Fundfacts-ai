"""Step 1 - Guardrails. Pure functions, no I/O, run before retrieval or any LLM call.

Order: PII -> advice -> returns. A message that mixes a factual question with advice
("expense ratio of X and should I buy it?") is refused - the refusal wins.
The user's text is never logged, stored, or echoed back in a refusal.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from fundfacts.schemas import AnswerType

EDU_ADVICE = ("https://www.amfiindia.com/investor/knowledge-center-info?zoneName=riskInMutualFunds",
              "AMFI - Risks in Mutual Funds")
EDU_PII = ("https://investor.sebi.gov.in/Investor-charter.html", "SEBI - Investor Charter")

PII_PATTERNS = {
    "PAN": re.compile(r"\b[A-Za-z]{5}\d{4}[A-Za-z]\b"),
    "Aadhaar number": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    "phone number": re.compile(r"(?:\+?91[\s-]?)?\b[6-9]\d{9}\b"),
    "email address": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "OTP": re.compile(r"\b(otp|one[\s-]?time[\s-]?password)\b", re.I),
    "account or folio number": re.compile(r"\b\d{8,18}\b"),
}
PII_PHRASES = re.compile(
    r"\b(my|mine|our)\s+(pan|aadhaa?r|folio|account(\s+number)?|bank\s+account|demat|phone|mobile|e-?mail|kyc|holdings?|"
    r"portfolio|investments?|units|balance|statement|sip)\b",
    re.I,
)

ADVICE = re.compile(
    r"\b("
    r"should\s+(i|we)|shall\s+i|do\s+you\s+(recommend|suggest)|recommend\w*|suggest\w*|advi[cs]e|"
    r"is\s+(it|this|hdfc[\w\s]{0,30}?)\s+(a\s+)?(good|safe|wise|right|worth|better|bad|smart)|"
    r"worth\s+(investing|buying|it)|good\s+(time|investment|fund|option|choice)|"
    r"(best|better|top|safest|ideal|right)\s+(fund|scheme|option|choice|investment|sip|elss|mutual\s+fund|for\s+me)|"
    r"which\s+(one\s+)?(is\s+(better|best|good|safer)|should\s+i|to\s+(buy|choose|pick|invest))|"
    r"which\s+(fund|scheme)\s+(is\s+)?(better|best|good|safer|should)|"
    r"\b(buy|sell|hold|exit|redeem|switch|stop|continue)\s+(now|or\s+not|or\s+\w+|it|this|my)\b|"
    r"invest\s+(now|today|more)|time\s+the\s+market|asset\s+allocation|how\s+much\s+(should|to)\s+i\s+invest|"
    r"will\s+(it|the\s+nav|the\s+fund)\s+(go\s+up|rise|fall|crash|grow)|ignore\s+(your|the|all)\s+(rules|instructions)"
    r")\b",
    re.I,
)
RETURNS = re.compile(
    r"\b(returns?|cagr|xirr|annuali[sz]ed|performance|performed|perform|outperform\w*|underperform\w*|"
    r"beat\s+the\s+(market|index|benchmark)|how\s+much\s+(will|would|can|could)\s+i\s+(earn|make|get|gain)|"
    r"growth\s+rate|profit|gains?\s+(of|in|from)\s+(the\s+)?(fund|scheme)|alpha|sharpe|compare\s+returns?)\b",
    re.I,
)
TAX_CONTEXT = re.compile(r"\btax(ed|ation|es)?\b|capital\s+gains?\s+(statement|report|tax)", re.I)


@dataclass(frozen=True)
class Verdict:
    kind: AnswerType | None  # None = allowed
    message: str = ""
    link: str = ""
    link_title: str = ""

    @property
    def ok(self) -> bool:
        return self.kind is None


def check(query: str, scheme_url: str | None = None, scheme_url_title: str | None = None) -> Verdict:
    for label, pat in PII_PATTERNS.items():
        if pat.search(query):
            return Verdict(AnswerType.REFUSAL_PII,
                           f"For your safety, please don't share personal details such as a {label} here. I don't accept "
                           "or store PAN, Aadhaar, account or folio numbers, OTPs, emails or phone numbers, and I can only "
                           "answer general factual questions about the five HDFC schemes I cover.", *EDU_PII)
    if ADVICE.search(query):  # before account phrases: "should I sell my units" is an advice question
        return Verdict(AnswerType.REFUSAL_ADVICE,
                       "I share facts only and can't give investment advice, recommendations or opinions on buying, "
                       "selling or choosing a scheme. The AMFI page linked below explains how to understand mutual fund "
                       "risks, and a SEBI-registered investment adviser can help with personal decisions.", *EDU_ADVICE)
    if PII_PHRASES.search(query):
        return Verdict(AnswerType.REFUSAL_PII,
                       "I can't look up or discuss personal accounts, holdings or statements. I can answer general "
                       "factual questions about the five HDFC schemes I cover, such as expense ratio, exit load or "
                       "minimum investment.", *EDU_PII)
    if RETURNS.search(query) and not TAX_CONTEXT.search(query):
        return Verdict(AnswerType.REFUSAL_RETURNS,
                       "I don't share, calculate or compare returns or performance. The scheme's official document "
                       "linked below has the latest published performance with the required disclosures.",
                       scheme_url or "https://files.hdfcfund.com/s3fs-public/2026-10/HDFC%20MF%20Factsheet%20-%20September%202026.pdf",
                       scheme_url_title or "HDFC MF Factsheet - September 2026")
    return Verdict(None)
