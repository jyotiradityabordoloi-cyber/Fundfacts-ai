"""HTML -> clean text blocks (one logical page per HTML document)."""
from __future__ import annotations

import html as html_lib
import re

from bs4 import BeautifulSoup

BLOCK_TAGS = ["h1", "h2", "h3", "h4", "p", "li", "td", "th"]
DROP_TAGS = ["script", "style", "noscript", "svg", "nav", "header", "footer", "form", "button", "iframe"]

# Lines that are site chrome, not content.
NOISE = re.compile(
    r"^(home|skip to (main )?content|menu|search|login|sign in|english|hindi|share|print|"
    r"read more|load more|more details are loading|back to top|\W*)$",
    re.I,
)
# Per-source trimming: content starts after / ends before these markers.
START_AFTER = {"sebi_elss": "Content"}
END_BEFORE = ["Related Articles", "Was this helpful", "Disclaimer:", "© "]


def clean(text: str) -> str:
    text = html_lib.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def html_blocks(raw_html: str) -> list[str]:
    """Visible text of block elements; inline links stay inside their sentence."""
    soup = BeautifulSoup(raw_html, "lxml")
    for t in soup(DROP_TAGS):
        t.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    blocks: list[str] = []
    for el in root.find_all(BLOCK_TAGS):
        if el.find(BLOCK_TAGS):  # container of other blocks: emit the children instead
            continue
        txt = clean(el.get_text(" ", strip=True))
        if txt and not NOISE.match(txt):
            blocks.append(txt)
    return blocks


def html_title(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "lxml")
    h1 = soup.find("h1")
    if h1 and clean(h1.get_text(" ")):
        return clean(h1.get_text(" "))
    return clean(soup.title.string) if soup.title and soup.title.string else ""


def parse_html(source_id: str, raw_html: str) -> tuple[str, str]:
    """Return (title, text). Blocks are de-duplicated and trimmed per source rules."""
    blocks = html_blocks(raw_html)
    marker = START_AFTER.get(source_id)
    if marker and marker in blocks:
        blocks = blocks[blocks.index(marker) + 1:]
    kept, seen = [], set()
    for b in blocks:
        if any(b.startswith(m) for m in END_BEFORE):
            break
        if b in seen:  # banners repeated on AMFI pages
            continue
        seen.add(b)
        kept.append(b)
    return html_title(raw_html), "\n".join(kept)
