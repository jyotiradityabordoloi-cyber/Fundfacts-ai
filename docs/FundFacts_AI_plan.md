# FundFacts AI: architecture and implementation plan

FundFacts AI is a facts-only mutual fund FAQ assistant inspired by the Groww product experience. It is an independent student project, not affiliated with Groww or HDFC.

**Status:** plan for review. Each phase is implemented only after approval.

## Scope
- **AMC:** HDFC Mutual Fund. **Schemes (Direct, Growth):** Large Cap, Flexi Cap, ELSS Tax Saver, Small Cap, Balanced Advantage.
- **Sources:** 15–25 official public URLs from the AMC, SEBI or AMFI only.
- **Stack:** Python, ChromaDB, Sentence Transformers (all-MiniLM-L6-v2), Claude (Anthropic) as the LLM.
- **Hosting:** Vercel. Code and docs on GitHub.

## Core requirements
1. Answer factual mutual fund questions only.
2. Every answer contains exactly one verified source URL.
3. Answers are at most three sentences.
4. Refuse investment recommendations.
5. Never invent missing facts or citations.
6. Reject PII and never store it.
7. Show "Last updated from sources".
8. Never calculate or compare returns.

## Hosting decision: Vercel, not Streamlit
Vercel runs short-lived serverless functions. Streamlit needs a long-running server with websockets, so it cannot be hosted on Vercel. The UI is therefore:

- `public/index.html`: a static single-page chat UI, served by Vercel's CDN.
- `api/index.py`: a FastAPI app that becomes the `/api/*` serverless function.

Two Vercel constraints shape the runtime:

| Constraint | Consequence |
|---|---|
| ~250 MB function bundle; PyTorch alone exceeds it | The query is embedded with the **same** all-MiniLM-L6-v2 weights in ONNX format via `onnxruntime`. Equivalence is verified: cosine similarity 1.0 against sentence-transformers. |
| No persistent server or disk; a ChromaDB server can't run in a function | Ingestion writes ChromaDB as the system of record. It then exports the identical collection (ids, text, metadata, vectors) to `vector_store/index.json`, which the function searches with NumPy. Locally, the app queries ChromaDB directly. |

## Source constraint: AMC / SEBI / AMFI only
`hdfcfund.com` returns HTTP 403 to automated requests. This was tested on 10 pages: scheme pages, KIM/SID hubs and TER disclosures. Scheme facts will therefore come from:

1. HDFC's own document server **`files.hdfcfund.com`**, which allows automated downloads: the five SIDs (21 Nov 2025), the Common Equity KIM (28 Nov 2025) and the monthly factsheet (Sept 2026).
2. Fallback (approved): the owner manually saves the `hdfcfund.com` page or PDF into `data/manual/`, with its URL recorded in the registry.

Concept and how-to content comes from SEBI (MF investor FAQ PDF, Investor Charter, ELSS guide) and AMFI (knowledge-centre articles, investor booklet).

## 1. System architecture

```
INGESTION (offline, re-runnable; every stage written to disk)
 sources.yaml ─► fetch ─► parse ─► extract facts ─► chunk ─► embed ─► ChromaDB ─► index.json export
 (allowlist)     raw/     docs/    facts.json       chunks/  MiniLM   vector_store/   (for Vercel)
                                   (field, value,                     + build_report.json
                                    page, quote)                        (counts, gaps, failures)

QUERY (FastAPI on Vercel: POST /api/chat)
 question ─► 1 Guardrails: PII / advice / returns  ──► polite refusal + educational link
              ▼ ok
            2 Intent + scheme detection (rules: which fact? which scheme?)
              ▼
            3a Fact lookup (structured, exact)  ── hit ──► template answer + quote
              ▼ miss
            3b Vector retrieval (same MiniLM; scheme metadata filter; top-k)
              ▼
            4 LLM (Claude), context-only → JSON {answer, chunk_id} or NOT_FOUND
              ▼
            5 Verifier: cited chunk was retrieved · URL is in the registry ·
              every number in the answer appears in the cited chunk · ≤ 3 sentences
              ▼ fail → NOT_FOUND (never guess)
            6 Response: answer · one URL · last updated · evidence (chunk ids, scores, quote)
```

**Explainable retrieval.** Every response carries an `evidence` list. The UI shows it in a "Why this answer" panel.

## 2. Folder structure

```
fundfacts-ai/
├── api/index.py                # FastAPI → Vercel function (/api/chat, /api/meta, /api/health)
├── public/index.html           # static UI (welcome line, 3 examples, disclaimer, evidence panel)
├── config.yaml                 # models, paths, top_k, thresholds, provider
├── .env.example                # ANTHROPIC_API_KEY, CLAUDE_MODEL (real .env never committed)
├── sources.yaml                # source registry = allowlist
├── fundfacts/
│   ├── config.py  schemas.py
│   ├── ingest/  fetch.py  parse_html.py  parse_pdf.py  extract_facts.py  chunk.py  embed_store.py
│   ├── query/   guardrails.py  intent.py  fact_lookup.py  retriever.py  verifier.py  answer.py
│   ├── llm/     claude_client.py
│   └── embed.py                # sentence-transformers (ingest) | ONNX (Vercel), same model
├── scripts/  run_ingest.py  make_sample_qa.py
├── data/  raw/  manual/  docs/  facts/  chunks/  build_report.json
├── vector_store/  chroma/  index.json
├── tests/  test_guardrails.py  test_fact_extraction.py  test_verifier.py  test_eval_set.py
├── eval/questions.yaml         # gold question → expected field / value / source
├── docs/  PRD.md  architecture.md  SOURCES.md  SAMPLE_QA.md  DISCLAIMER.md
├── requirements.txt            # runtime only (Vercel): fastapi, numpy, onnxruntime, tokenizers, httpx, pydantic, pyyaml
├── requirements-ingest.txt     # + chromadb, sentence-transformers, pypdf, pdfplumber, bs4, lxml, requests, pytest
└── vercel.json
```

## 3. Dependencies
| Purpose | Packages |
|---|---|
| Runtime (Vercel) | fastapi, pydantic, pyyaml, httpx, numpy, onnxruntime, tokenizers, python-dotenv |
| Ingestion / local | chromadb, sentence-transformers, requests, beautifulsoup4, lxml, pypdf, pdfplumber, pytest, uvicorn |
| LLM | Claude via the Anthropic Messages API (httpx) |

No LangChain: the pipeline is small, and plain code is easier to explain and debug.

## 4. Data schema
| Record | Fields |
|---|---|
| **Source** (`sources.yaml`) | `source_id`, `url`, `publisher` (AMC/SEBI/AMFI), `doc_type` (KIM/SID/FAQ/article/circular), `scheme_id`, `status` (active/blocked/manual/historical), `notes` |
| **RawFetch** | `source_id`, `fetched_at`, `http_status`, `sha256`, `path`, `content_type` |
| **Document** | `source_id`, `title`, `doc_date` (as-of date printed in the document), `pages: [{n, text}]` |
| **Fact** | `scheme_id`, `field` (enum: expense_ratio, exit_load, min_sip, min_lumpsum, lock_in, riskometer, benchmark, fund_manager, category), `value`, `as_of`, `source_id`, `page`, `quote` |
| **Chunk** | `chunk_id`, `source_id`, `scheme_id\|null`, `page`, `section`, `text`, `char_span` (metadata mirrored into Chroma) |
| **Answer** | `type` (answer / refusal_advice / refusal_returns / refusal_pii / not_found), `text`, `source_url`, `last_updated`, `evidence: [{chunk_id, score, quote}]`, `path` (fact / rag) |

User questions are never written to disk or logs, so "never store PII" holds by construction.

## 5. Implementation plan (one phase per approval)
| Phase | Deliverable | Done when |
|---|---|---|
| 0 | Decisions, skeleton, config, schemas | Config validates; repo builds |
| 1 | Source registry: 15–25 verified AMC/SEBI/AMFI URLs, including a KIM/SID per scheme | Every URL fetched, or marked blocked/manual with a reason |
| 2 | Fetch + parse (HTML, PDF) | `data/docs/` filled; `build_report.json` |
| 3 | Fact extraction for the 5 schemes | Each field has value + page + quote, or is explicitly missing; unit tests |
| 4 | Chunk + embed + ChromaDB + export | Chroma count = chunks on disk = export count |
| 5 | Guardrails + intent + fact lookup | Guardrail tests pass |
| 6 | Retrieval + LLM adapters + verifier | Eval set: correct source ≥ 90%; 0 unverified numbers |
| 7 | UI (static HTML + FastAPI) | Welcome line, 3 examples, disclaimer, evidence panel |
| 8 | Docs, sample Q&A, GitHub push, Vercel deploy | Public Vercel URL works |

## Open decisions
1. Repo: a fresh `fundfacts-ai` repo, or restructure the current one?
