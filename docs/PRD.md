# PRD: FundFacts AI

| | |
|---|---|
| **Product** | FundFacts AI, a facts-only mutual fund FAQ assistant |
| **Type** | Independent student project, inspired by the Groww product experience (not affiliated with Groww or HDFC) |
| **Owner** | Jyotiraditya Bordoloi |
| **Status** | Draft for review |
| **Last updated** | 09 Nov 2026 |
| **Related docs** | [ProblemStatement.txt](ProblemStatement.txt) · [FundFacts_AI_plan.md](FundFacts_AI_plan.md) · architecture.md · implementation.md |

---

## 1. Problem
Retail investors comparing mutual fund schemes ask the same factual questions again and again. What is the expense ratio? Is there an exit load? What is the minimum SIP? How long is the ELSS lock-in? What is the riskometer level or benchmark? How do I download my statement?

The answers are spread across long KIM/SID PDFs, regulator pages and AMC disclosures. General chatbots answer quickly but often invent numbers, cite nothing, or slide into investment advice. Support and content teams spend time on these repetitive questions.

## 2. Goal
Answer factual questions about five HDFC Mutual Fund schemes in **three sentences or fewer**, each with **one verified official source link** and a **"Last updated from sources"** date. Refuse advice, never make up facts, and never collect personal data.

### Non-goals
- Investment advice, recommendations, suitability, or "which fund is better".
- Calculating, projecting or comparing returns or performance.
- Account-specific help: holdings, transactions, KYC status, statements for a specific person.
- AMCs other than HDFC Mutual Fund, or schemes outside the five in scope.
- Real-time data. NAV and AUM change daily; FundFacts reflects the last ingestion.

## 3. Users
| Persona | Need | Example question |
|---|---|---|
| **Retail investor** comparing schemes | One specific fact, fast, from a trustworthy source | "What is the exit load of HDFC Small Cap Fund?" |
| **First-time ELSS investor** | Understand lock-in and tax-saving rules | "What is the lock-in period for HDFC ELSS Tax Saver?" |
| **Existing investor** | Know where to get documents | "How do I get my Consolidated Account Statement?" |
| **Support / content team** | Consistent, cited answers to repetitive questions | "What is the benchmark of HDFC Flexi Cap?" |

## 4. Scope

### 4.1 AMC and schemes
**AMC:** HDFC Mutual Fund. **Schemes (Direct plan, Growth option):**

| # | Scheme | Category |
|---|---|---|
| 1 | HDFC Large Cap Fund | Large Cap |
| 2 | HDFC Flexi Cap Fund | Flexi Cap |
| 3 | HDFC ELSS Tax Saver Fund | ELSS |
| 4 | HDFC Mid Cap Fund | Mid Cap |
| 5 | HDFC Small Cap Fund | Small Cap |

### 4.2 Questions in scope
| Fact type | Example |
|---|---|
| Expense ratio (TER) | "Expense ratio of HDFC Flexi Cap?" |
| Exit load | "Exit load for HDFC Mid Cap Fund?" |
| Minimum SIP / lumpsum | "Minimum SIP for HDFC Small Cap?" |
| Lock-in | "ELSS lock-in?" |
| Riskometer | "Risk level of HDFC Large Cap?" |
| Benchmark | "Benchmark of HDFC ELSS Tax Saver?" |
| Category / objective / fund manager | "What does HDFC Flexi Cap invest in?" |
| Statements and documents | "How do I download a capital gains statement / CAS?" |
| General MF concepts | "What is NAV?", "What is TER?", "What is a riskometer?" |

### 4.3 Sources
- **15–25 official public URLs from the AMC (HDFC Mutual Fund), SEBI or AMFI only.** No third-party blogs, aggregators, news sites or app screenshots.
- Each source is registered in `sources.yaml` with its publisher, document type, scheme and status. Only registered URLs are fetched; no links are followed.
- **Known constraint:** the `www.hdfcfund.com` website returns HTTP 403 to automated requests. HDFC's own document server `files.hdfcfund.com` does not, so scheme facts come from the official SIDs (21 Nov 2025), the Common Equity KIM (28 Nov 2025) and the monthly factsheet (Sept 2026). The two investor-service pages on `www.hdfcfund.com` (statement requests, CAS) are saved manually by the owner into `data/manual/`; their URLs stay the citations.
- Historical or superseded documents are excluded from the active corpus (e.g. the SEBI categorisation PDF from Oct 2017).

## 5. Functional requirements

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| **FR1** | Answer factual mutual fund questions only, from the corpus | Must | Each answer is supported by a retrieved passage or extracted fact |
| **FR2** | Exactly **one verified source URL** per answer | Must | The URL is in the source registry and belongs to the passage or fact the answer used |
| **FR3** | Answers are **≤ 3 sentences** | Must | Enforced in post-processing; extra sentences are cut |
| **FR4** | Show **"Last updated from sources: <date>"** | Must | Date = the source's retrieval date (IST); the document's as-of date is shown when known |
| **FR5** | **Refuse investment recommendations** politely | Must | "Should I buy/sell", "best fund", "which is better", "worth investing" → refusal + educational link (AMFI/SEBI) |
| **FR6** | **No invented facts or citations** | Must | Every number in an answer must appear in the cited passage; otherwise "not found" |
| **FR7** | **Reject PII and never store it** | Must | PAN, Aadhaar, account/folio numbers, OTPs, emails and phone numbers → refusal; the query is never logged or saved |
| **FR8** | **No return calculation or comparison** | Must | Returns/CAGR/"how much will I earn" → refusal + link to the official scheme document; return data is not ingested |
| **FR9** | Handle unknown or off-topic questions | Must | "Not in my sources" message + AMC/AMFI link |
| **FR10** | Explainable retrieval | Should | Each response includes evidence (passage ids, scores, short quote), shown in a "Why this answer" panel |
| **FR11** | Minimal UI | Must | Welcome line, 3 example questions, note "Facts-only. No investment advice." |
| **FR12** | Configurable LLM, free by default | Must | Google Gemini free tier by default, Claude optional, no-LLM mode with no key; provider and model set via config/env without code changes |
| **FR13** | Works without an LLM key | Should | Structured-fact answers and extractive fallback still return cited answers |
| **FR14** | Re-runnable ingestion, each stage saved | Must | Raw → parsed → facts → chunks → embeddings → ChromaDB, all persisted with a build report |

### Answer contract
Every answer has this shape:

```json
{
  "type": "answer | refusal_advice | refusal_returns | refusal_pii | not_found",
  "text": "≤ 3 sentences",
  "source_url": "one URL from the registry",
  "last_updated": "09 Nov 2026",
  "evidence": [{"chunk_id": "...", "score": 0.91, "quote": "..."}],
  "path": "fact | rag"
}
```

### Refusal copy
| Case | Message (summary) | Link |
|---|---|---|
| Advice | "I can share facts only and can't give investment advice or recommendations…" | AMFI/SEBI investor education |
| Returns | "I don't share, compute or compare returns…" | The scheme's official document |
| PII | "For your safety, please don't share personal details… I don't accept or store them." | SEBI Investor Charter |
| Not found | "I couldn't find that in my official sources…" | AMC/AMFI page |

## 6. Non-functional requirements
| Area | Requirement |
|---|---|
| **Accuracy** | ≥ 95% of scheme-fact answers correct on the evaluation set; 0 unverified numbers |
| **Citation quality** | ≥ 90% of answers cite the expected source |
| **Safety** | 100% of the advice/returns/PII test cases refused |
| **Latency** | p50 < 3 s for a warm request; first request after idle < 15 s |
| **Privacy** | No user input stored or logged; no cookies or analytics that capture questions |
| **Maintainability** | Config-driven (models, thresholds, provider); one command rebuilds the corpus; plain Python, no heavy frameworks |
| **Cost** | Free hosting tier; one LLM call per answer at most; cached model load |
| **Accessibility** | Keyboard usable, readable contrast in light and dark mode, works at phone width |

## 7. Solution overview
- **Ingestion (offline):** fetch registered URLs → parse HTML/PDF → extract structured scheme facts with page and quote → chunk → embed with `sentence-transformers/all-MiniLM-L6-v2` → store in **ChromaDB**.
- **Query path:**
  1. Guardrails (PII, advice, returns).
  2. Intent and scheme detection.
  3. **Exact fact lookup** first.
  4. Otherwise, vector retrieval and an LLM that answers from context only.
  5. A **verifier** checks the citation and every number.
  6. The response goes out.
- **Hosting:** **Vercel**. A static HTML UI is served from the CDN, and a FastAPI serverless function exposes `/api/chat`. On Vercel, queries are embedded with the same MiniLM weights in ONNX, and retrieval runs over an exact export of the ChromaDB collection. Code and docs are on **GitHub**, and Vercel redeploys on every push.

Full design: [FundFacts_AI_plan.md](FundFacts_AI_plan.md).

## 8. UX
- **Header:** product name + "Facts-only" badge.
- **Banner:** "Facts-only. No investment advice." plus a PII warning.
- **Welcome card:** one welcome line, 3 clickable example questions, and the list of schemes covered.
- **Answer card:** answer text, source link (opens in a new tab), "Last updated from sources", and a collapsible "Why this answer".
- **Refusal card:** a visible tag (Facts only / No performance claims / Privacy) and the educational link.
- **Footer disclaimer:** "Mutual fund investments are subject to market risks; read all scheme-related documents carefully."

## 9. Success metrics
| Metric | Target | How measured |
|---|---|---|
| Fact accuracy | ≥ 95% | `eval/questions.yaml` gold set (≥ 30 questions) |
| Correct citation | ≥ 90% | Same eval set |
| Guardrail recall | 100% | `tests/test_guardrails.py` |
| Hallucinated numbers | 0 | Verifier + eval |
| Answer length | 100% ≤ 3 sentences | Automated check |
| Uptime of demo link | Available during review | Vercel deployment |

## 10. Deliverables
1. Working prototype link (Vercel).
2. Source list: `sources.yaml` + `SOURCES.md`, 15–25 URLs with publisher, type and retrieval date.
3. README: setup, scope (AMC + schemes), architecture summary, known limits.
4. Sample Q&A: `SAMPLE_QA.md`, 5–10 queries with answers and links, including refusals.
5. Disclaimer snippet: `DISCLAIMER.md`.
6. Docs: ProblemStatement, PRD, architecture, implementation.

## 11. Risks and mitigations
| Risk | Impact | Mitigation |
|---|---|---|
| `hdfcfund.com` blocks scraping | No AMC-page facts | Use HDFC's document server `files.hdfcfund.com` (SIDs, KIM, factsheet); manual download into `data/manual/` for the two service pages |
| KIM/SID values are dated (e.g. TER changes) | Stale facts | Show the document's as-of date; re-run ingestion; README states the snapshot nature |
| PDF tables parse poorly | Missing or wrong facts | `pdfplumber` for tables; per-field unit tests; mark a field "missing" rather than guess |
| LLM invents numbers or sources | Wrong answers | Exact fact lookup first; context-only prompt; numeric verifier; NOT_FOUND fallback |
| Regex guardrails miss unusual phrasing | Advice or PII slips through | Test suite with paraphrases; conservative patterns; LLM prompt also forbids advice |
| Vercel cold start / bundle limits | Slow first answer | ONNX runtime instead of PyTorch; small exported index |
| LLM key quota or outage | No generated answers | Fact lookup + extractive fallback still cite sources |

## 12. Open questions
1. Repository: a new `fundfacts-ai` repo, or replace the current project?

## 13. Milestones
| Phase | Output |
|---|---|
| 0 | Decisions, skeleton, config, schemas |
| 1 | Verified source registry (15–25 URLs) |
| 2 | Fetch + parse |
| 3 | Structured fact extraction (5 schemes) |
| 4 | Chunk, embed, ChromaDB, export |
| 5 | Guardrails, intent, fact lookup |
| 6 | Retrieval, LLM adapters, verifier, evaluation |
| 7 | UI |
| 8 | Docs, sample Q&A, GitHub, Vercel deploy |

Each phase starts only after the previous one is reviewed and approved.
