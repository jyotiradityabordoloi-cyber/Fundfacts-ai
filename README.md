# FundFacts AI

FundFacts AI is a facts-only mutual fund FAQ assistant for five HDFC Mutual Fund schemes: Large Cap, Flexi Cap, ELSS Tax Saver, Mid Cap and Small Cap (Direct, Growth). It answers only from official AMC, SEBI and AMFI sources. Each answer is at most three sentences and cites one verified source.

> **Facts-only. No investment advice.** This is an independent student project inspired by the Groww product experience. It is not affiliated with Groww or HDFC Mutual Fund.

**Status:** Phases 1-9 of 10 are complete: config, scraping (`python -m fundfacts.ingest.fetch`), loading (`python -m fundfacts.ingest.load`, performance sections removed) and fact extraction (`python -m fundfacts.ingest.extract_facts` → `data/facts/facts.json`, 43/50 facts found with page + quote), and chunking (`python -m fundfacts.ingest.chunk` → `data/chunks/chunks.json`, 2,029 chunks incl. 43 fact cards), and embeddings (`python -m fundfacts.ingest.embed` → `data/embeddings/embeddings.json`, all-MiniLM-L6-v2, 384-d), and the vector store (`python -m fundfacts.ingest.store` → ChromaDB in `vector_store/chroma/`, verified, exported to `vector_store/index.json`, report in `data/build_report.json`), and the answer pipeline (guardrails → intent → exact fact lookup → retrieval → Claude or extractive fallback → verifier). Try it: `python scripts/ask.py "What is the exit load of HDFC Small Cap Fund?"`. Evaluation: 40 gold questions, 100% fact and source accuracy (`eval/last_run.json`). The web app runs locally with `uvicorn api.index:app --port 8000` (open http://127.0.0.1:8000).

## Docs
- [Problem statement](docs/ProblemStatement.txt)
- [PRD](docs/PRD.md)
- [Architecture](docs/architecture.md)
- [Implementation plan](docs/implementation.md)

## Setup
Requires Python 3.11+.

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements-ingest.txt
```

```bash
copy .env.example .env
```

Then add your `ANTHROPIC_API_KEY` to `.env`.

## Phase 1 commands
Print the validated configuration (the API key is masked):

```bash
python -m fundfacts.config
```

Summarise the source registry and check every URL and manual file. This saves nothing:

```bash
python -m fundfacts.sources --check
```

Run the tests:

```bash
python -m pytest -q
```

## Sources
The source list is [`sources.yaml`](sources.yaml): 20 ingested sources (9 HDFC Mutual Fund, 3 SEBI, 8 AMFI).
- **HDFC scheme documents** come from HDFC's document server `files.hdfcfund.com`: five SIDs, the Common Equity KIM and the monthly factsheet.
- **The `www.hdfcfund.com` website** blocks automated requests. Its two investor-service pages (statement requests, CAS) are saved by hand into `data/manual/`:
  - `data/manual/hdfc_request_statement.html` ← https://www.hdfcfund.com/services/additional-info/request-statement
  - `data/manual/hdfc_cas.html` ← https://www.hdfcfund.com/services/consolidated-account-statement
