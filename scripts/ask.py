"""Ask FundFacts AI from the command line.

    python scripts/ask.py "What is the exit load of HDFC Small Cap Fund?"
    python scripts/ask.py --evidence "What is a consolidated account statement?"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from fundfacts.query.answer import answer  # noqa: E402


def main(argv: list[str]) -> None:
    show = "--evidence" in argv
    question = " ".join(a for a in argv if a != "--evidence")
    a = answer(question)
    print(f"[{a.type.value} via {a.path}] {a.text}")
    if a.source_url:
        print(f"  Source: {a.source_title} - {a.source_url}")
    if a.last_updated:
        print(f"  Last updated from sources: {a.last_updated}")
    if show:
        for e in a.evidence:
            print(f"  evidence {e.score:.3f} {e.chunk_id} {e.adjustments}")


if __name__ == "__main__":
    main(sys.argv[1:])
