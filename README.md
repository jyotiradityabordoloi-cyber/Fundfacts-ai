# FundFacts AI

FundFacts AI is a facts-only mutual fund FAQ assistant for five HDFC Mutual Fund schemes: Large Cap, Flexi Cap, ELSS Tax Saver, Mid Cap and Small Cap (Direct, Growth). It answers only from official AMC, SEBI and AMFI sources. Each answer is at most three sentences and cites one verified source.

> **Facts-only. No investment advice.** This is an independent student project inspired by the Groww product experience. It is not affiliated with Groww or HDFC Mutual Fund.

**Status:** Phases 1-2 of 10 are complete: project skeleton, config, schemas, source registry, and scraping (`python -m fundfacts.ingest.fetch` writes `data/raw/` + `manifest.json`). See [docs/implementation.md](docs/implementation.md).

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
The source list is [`sources.yaml`](sources.yaml): 19 ingested sources (9 HDFC Mutual Fund, 3 SEBI, 7 AMFI).
- **HDFC scheme documents** come from HDFC's document server `files.hdfcfund.com`: five SIDs, the Common Equity KIM and the monthly factsheet.
- **The `www.hdfcfund.com` website** blocks automated requests. Its two investor-service pages (statement requests, CAS) are saved by hand into `data/manual/`:
  - `data/manual/hdfc_request_statement.html` ← https://www.hdfcfund.com/services/additional-info/request-statement
  - `data/manual/hdfc_cas.html` ← https://www.hdfcfund.com/services/consolidated-account-statement
