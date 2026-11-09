# FundFacts AI

**FundFacts AI is a facts-only mutual fund FAQ assistant for five HDFC Mutual Fund schemes.** It answers questions like "What is the expense ratio?", "Is there an exit load?", "What is the ELSS lock-in?" and "What is the benchmark?". Answers come only from official HDFC Mutual Fund, SEBI and AMFI documents. Each answer is **at most three sentences** and cites **one verified source**, with **"Last updated from sources"**. It never gives advice and never quotes returns.

> **Facts-only. No investment advice.** An independent student project inspired by the Groww product experience. It is not affiliated with Groww or HDFC Mutual Fund.

- **Live app:** https://fundfacts-ai-ten.vercel.app. General questions there are written by **Google Gemini Flash-Lite (free tier)** and verified against the cited source; scheme facts come from the fact table. The 40-question evaluation scores 40/40 against the live deployment with Gemini on.
- **Deliverables:**
  - [SOURCES.md](SOURCES.md) and [sources.csv](sources.csv): the source list
  - [SAMPLE_QA.md](SAMPLE_QA.md): real answers and refusals
  - [DISCLAIMER.md](DISCLAIMER.md): the disclaimer text used in the UI
  - [eval/last_run.json](eval/last_run.json): evaluation results
- **Design docs:** [Problem statement](docs/ProblemStatement.txt) · [PRD](docs/PRD.md) · [Architecture](docs/architecture.md) · [Implementation plan](docs/implementation.md)

## Scope
| | |
|---|---|
| AMC | HDFC Mutual Fund |
| Schemes (Direct, Growth) | HDFC Large Cap Fund, HDFC Flexi Cap Fund, HDFC ELSS Tax Saver Fund, HDFC Small Cap Fund, HDFC Balanced Advantage Fund |
| Sources | 20 registered official URLs (HDFC Mutual Fund, SEBI, AMFI); 18 ingested automatically, 2 via manual download ([SOURCES.md](SOURCES.md)) |
| Facts | Expense ratio, exit load, minimum SIP, minimum lumpsum, lock-in, riskometer, benchmark, fund managers, category, objective; plus SEBI/AMFI concepts (NAV, CAS, ELSS, TER) |

## How it works
RAG pipeline in which every stage writes its output to disk, so each step can be inspected:

| Phase | Command | Output |
|---|---|---|
| Scrape (registered URLs only, no link following) | `python -m fundfacts.ingest.fetch` | `data/raw/` + `manifest.json` |
| Load (performance sections removed) | `python -m fundfacts.ingest.load` | `data/docs/*.json` |
| Extract facts (value + page + verbatim quote) | `python -m fundfacts.ingest.extract_facts` | `data/facts/facts.json` |
| Chunk (fact cards + page-bounded passages) | `python -m fundfacts.ingest.chunk` | `data/chunks/chunks.json` |
| Embed (`sentence-transformers/all-MiniLM-L6-v2`) | `python -m fundfacts.ingest.embed` | `data/embeddings/embeddings.json` |
| Store in ChromaDB + verify + export | `python -m fundfacts.ingest.store` | `vector_store/chroma/`, `vector_store/index.json`, `data/build_report.json` |

**Answering a question** (`fundfacts/query/`):
1. **Guardrails.** Personal data, advice requests and returns questions are refused politely, with an educational link.
2. **Intent.** Rules work out which scheme and which fact are being asked about.
3. **Exact fact lookup.** If the fact is in the fact table, the answer comes from that quoted line, with no AI writing.
4. **Retrieval.** ChromaDB search with the same embedding model, with an explained re-rank.
5. **Writing the answer.** An LLM writes it from the retrieved passages only: **Google Gemini (free tier)** by default, or Claude if you configure it. Without any key, the best sentences are quoted verbatim instead, also free.
6. **Verifier.**
   - The cited passage must have been retrieved.
   - The URL must be in the source registry.
   - **Every number must appear in the source.**
   - The answer must be at most 3 sentences, with no advice wording.

   If any check fails, the reply is "not found". The assistant never guesses.

Every response also lists its evidence (passage ids, scores, quote), shown in the UI as **"Why this answer"**.

**In the UI:**
- **Explore schemes** opens each scheme's fact sheet (every value with its source page and as-on date; missing facts listed, never guessed) with one-tap questions.
- **Ask about this scheme** sets the scheme for follow-ups like "exit load?". A scheme named in the question still wins, and concept questions are unaffected.
- **Theme toggle.** Black, green and white only: dark by default, with a light theme that is remembered per browser.

## Run it locally
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

Optionally, add a **free Gemini key** to `.env` as `GEMINI_API_KEY=...`. Create one at https://aistudio.google.com/app/apikey (no credit card needed). Without a key, the app quotes its sources verbatim instead of letting an LLM write the answer.

```bash
uvicorn api.index:app --port 8000
```

Open http://127.0.0.1:8000. To ask from the terminal instead:

```bash
python scripts/ask.py --evidence "What is the exit load of HDFC Small Cap Fund?"
```

To rebuild the whole corpus (about 5 minutes on CPU), run the six phases in the table above in order. Then regenerate the deliverables:

```bash
python scripts/make_docs.py
```

## Tests and evaluation

```bash
python -m pytest -q
```

There are 172 tests covering:
- configuration and the source registry
- scraping, loading and the removal of performance text
- every hand-checked fact value
- chunking, and that ChromaDB matches the Vercel export
- ONNX vs sentence-transformers parity
- guardrails, the verifier, edge cases and the API
- LLM provider selection, the Gemini request format and quota fallback
- running the API with only the Vercel runtime requirements installed

The evaluation set in [eval/questions.yaml](eval/questions.yaml) has **40 questions**, run without an LLM:

| Metric | Result | Target |
|---|---|---|
| Fact accuracy | 100% | ≥ 95% |
| Correct source cited | 100% | ≥ 90% |
| Refusals / not found correct | 100% | 100% |
| One link per answer, ≤ 3 sentences | yes | yes |

## Deploy on Vercel
The web page is static (`public/index.html`) and the API is a Python function (`api/index.py`). Vercel can't run PyTorch or a ChromaDB server inside a function, so the live app makes two substitutions:
- **Embeddings:** the **same MiniLM model in ONNX form** (identical vectors, which a test checks).
- **Search:** the **exact export of the ChromaDB collection** (`vector_store/index.json`).

Steps:
1. Push this repository to GitHub.
2. In Vercel, choose **Add New… → Project** and import the repository. Set **Framework Preset: Other**, with no build command.
3. Optional: under **Settings → Environment Variables**, add `GEMINI_API_KEY` (free, from Google AI Studio) so Gemini writes general-concept answers. Without it the app still works, for free.
4. Click **Deploy**. The first question after the app has been idle downloads the ONNX model (about 90 MB) into `/tmp`, so it takes a few seconds.

After that, every push to `main` redeploys automatically.

## Configuration
Everything is in [`config.yaml`](config.yaml), with environment overrides: `LLM_PROVIDER` (auto | gemini | anthropic | none), `GEMINI_API_KEY`, `GEMINI_MODEL` (default `gemini-flash-lite-latest`, Google's alias for the current Flash-Lite model, which is fast and the least congested on the free tier; if Google retires a model, the app switches to an available Flash model automatically), `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `EMBEDDING_BACKEND`, `VECTOR_DB`, `TOP_K`, `MIN_SIMILARITY`. In `auto` mode, Gemini is used if its key is set, then Claude, otherwise the free no-LLM mode. Secrets live only in `.env` and in Vercel's environment variables, never in the repository.

## Privacy and safety
- **Personal data:** PAN, Aadhaar, phone numbers, emails, OTPs and account/folio numbers are refused before any processing, and never echoed back.
- **Nothing is stored:** questions are not logged or stored. They're only sent to the configured LLM, and only after the guardrails pass. On Gemini's free tier, Google may use prompts to improve its products. Only the question and public document passages are ever sent.
- **No performance figures:** returns tables are removed from documents during loading. Return questions are refused with a link to the official document.

## Known limits
- **Seven facts are missing.** Minimum SIP is missing for 4 schemes and the riskometer for 3, because they're only stated in the schemes' Scheme Summary Documents, which sit behind the blocked `www.hdfcfund.com`. The assistant says "not found" instead of guessing. Saving those PDFs into `data/manual/` and re-running the pipeline fills the gaps.
- **Snapshot data.** Facts come from documents dated 21 Nov 2025 (SIDs), 28 Nov 2025 (KIM) and 30 Sep 2026 (factsheet). Re-run the pipeline when new documents are published.
- **Regex guardrails.** Guardrails and intent detection are rule-based. Unusual phrasing may be refused unnecessarily, or routed to search instead of the exact fact table.
- **Quoted answers without an LLM key.** Without a key, general questions get correct but verbatim answers. If the free Gemini quota runs out, the app falls back to verified quotes automatically. The "how to download a statement" pages need the two manual downloads.
- **Five schemes only.** Other HDFC schemes and other fund houses are politely declined.

## Project structure
```
api/index.py              FastAPI app (Vercel function)
public/index.html         web UI
fundfacts/ingest/         fetch, load, extract_facts, chunk, embed, store
fundfacts/query/          guardrails, intent, fact_lookup, retriever, verifier, answer
fundfacts/llm/            Gemini (free) and Claude clients + provider router
config.yaml  sources.yaml configuration and source registry
data/  vector_store/      every pipeline stage's output
tests/  eval/             tests and the gold evaluation set
docs/                     problem statement, PRD, architecture, implementation plan
```
