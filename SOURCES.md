# Sources

FundFacts AI uses only official public sources from **HDFC Mutual Fund (AMC), SEBI and AMFI**. The corpus has **20 registered sources** (18 ingested, 2 awaiting a manual download). Each URL is fetched exactly once per build and links inside pages are never followed. The registry is [`sources.yaml`](sources.yaml) and the machine-readable list is [`sources.csv`](sources.csv); this page is generated from them by `python scripts/make_docs.py`.

## Corpus

| # | Publisher | Type | Title | Scheme | Inventory | Status | Retrieved (IST) |
|---|---|---|---|---|---|---|---|
| 1 | AMC | SID | [Scheme Information Document - HDFC Large Cap Fund (21 Nov 2025)](https://files.hdfcfund.com/s3fs-public/SID/2025-11/SID%20-%20HDFC%20Large%20Cap%20Fund%20dated%20November%2021,%202025.pdf) | HDFC Large Cap Fund | replaces SRC-001, SRC-007 | ingested | 09 Nov 2026 |
| 2 | AMC | SID | [Scheme Information Document - HDFC Flexi Cap Fund (21 Nov 2025)](https://files.hdfcfund.com/s3fs-public/SID/2025-11/SID%20-%20HDFC%20Flexi%20Cap%20Fund%20dated%20November%2021,%202025.pdf) | HDFC Flexi Cap Fund | replaces SRC-002, SRC-007 | ingested | 09 Nov 2026 |
| 3 | AMC | SID | [Scheme Information Document - HDFC ELSS Tax Saver Fund (21 Nov 2025)](https://files.hdfcfund.com/s3fs-public/SID/2025-11/SID%20-%20HDFC%20ELSS%20Tax%20Saver%20Fund%20dated%20November%2021,%202025.pdf) | HDFC ELSS Tax Saver Fund | replaces SRC-003, SRC-007 | ingested | 09 Nov 2026 |
| 4 | AMC | SID | [Scheme Information Document - HDFC Small Cap Fund (21 Nov 2025)](https://files.hdfcfund.com/s3fs-public/SID/2025-11/SID%20-%20HDFC%20Small%20Cap%20Fund%20dated%20November%2021,%202025.pdf) | HDFC Small Cap Fund | replaces SRC-004, SRC-007 | ingested | 09 Nov 2026 |
| 5 | AMC | SID | [Scheme Information Document - HDFC Balanced Advantage Fund (21 Nov 2025)](https://files.hdfcfund.com/s3fs-public/SID/2025-11/SID%20-%20HDFC%20Balanced%20Advantage%20Fund%20dated%20November%2021,%202025.pdf) | HDFC Balanced Advantage Fund | replaces SRC-005, SRC-007 | ingested | 09 Nov 2026 |
| 6 | AMC | KIM | [Key Information Memorandum - HDFC equity schemes (28 Nov 2025)](https://files.hdfcfund.com/s3fs-public/2025-12/Common%20Equity%20KIM%20dated%20November%2028%2C%202025.pdf) | - | replaces SRC-006 | ingested | 09 Nov 2026 |
| 7 | AMC | factsheet | [HDFC MF Factsheet - September 2026](https://files.hdfcfund.com/s3fs-public/2026-10/HDFC%20MF%20Factsheet%20-%20September%202026.pdf) | - | replaces SRC-008, SRC-009, SRC-010 | ingested | 09 Nov 2026 |
| 8 | AMFI | SSD | [Scheme Summary Document - HDFC Small Cap Fund (AMFI)](https://portal.amfiindia.com/spages/SSD_8547.pdf) | HDFC Small Cap Fund | added | ingested | 09 Nov 2026 |
| 9 | AMC | guide | [HDFC Mutual Fund - Request Statement (account and capital gains statements)](https://www.hdfcfund.com/services/additional-info/request-statement) | - | added | manual download pending | - |
| 10 | AMC | guide | [HDFC Mutual Fund - Download Consolidated Account Statement](https://www.hdfcfund.com/services/consolidated-account-statement) | - | added | manual download pending | - |
| 11 | SEBI | FAQ | [SEBI - FAQs for Mutual Fund Investors (updated as on 31 Aug 2024)](https://www.sebi.gov.in/sebi_data/faqfiles/sep-2024/1727242783639.pdf) | - | SRC-011 | ingested | 09 Nov 2026 |
| 12 | SEBI | guide | [SEBI Investor - A Guide to ELSS](https://investor.sebi.gov.in/elss.html) | - | added | ingested | 09 Nov 2026 |
| 13 | SEBI | guide | [SEBI - Investor Charter](https://investor.sebi.gov.in/Investor-charter.html) | - | SRC-012 | ingested | 09 Nov 2026 |
| 14 | AMFI | article | [AMFI - Introduction to Mutual Funds](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=IntroductionMutualFunds) | - | SRC-018 | ingested | 09 Nov 2026 |
| 15 | AMFI | article | [AMFI - Types of Mutual Fund Schemes](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=TypesOfMutualFundSchemes) | - | SRC-019 | ingested | 09 Nov 2026 |
| 16 | AMFI | article | [AMFI - Expense Ratio](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=expenseRatio) | - | SRC-020 | ingested | 09 Nov 2026 |
| 17 | AMFI | article | [AMFI - Net Asset Value (NAV)](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=NetAssetValueNAV) | - | SRC-021 | ingested | 09 Nov 2026 |
| 18 | AMFI | article | [AMFI - Categorization of Mutual Fund Schemes](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=CategorizationOfMutualFundSchemes) | - | SRC-022 | ingested | 09 Nov 2026 |
| 19 | AMFI | article | [AMFI - Risks in Mutual Funds](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=riskInMutualFunds) | - | SRC-023 | ingested | 09 Nov 2026 |
| 20 | AMFI | guide | [AMFI - Understanding Mutual Funds (investor awareness booklet)](https://www.amfiindia.com/uploads/AMFI_Understanding_Mutual_Funds_IAP_Booklet_Final_Website_version_860a5b77aa.pdf) | - | SRC-024 | ingested | 09 Nov 2026 |

## Reviewed, not ingested

| Inventory | Publisher | Title | Decision | Reason | Re-checked |
|---|---|---|---|---|---|
| SRC-001 | AMC | [HDFC Large Cap Fund - Direct Plan (www.hdfcfund.com)](https://www.hdfcfund.com/explore/mutual-funds/hdfc-large-cap-fund/direct) | blocked | HTTP 403 to automated requests (re-checked 09 Nov 2026). | 2026-11-09 |
| SRC-002 | AMC | [HDFC Flexi Cap Fund - Direct Plan (www.hdfcfund.com)](https://www.hdfcfund.com/explore/mutual-funds/hdfc-flexi-cap-fund/direct) | blocked | HTTP 403 to automated requests (re-checked 09 Nov 2026). | 2026-11-09 |
| SRC-003 | AMC | [HDFC ELSS Tax Saver Fund - Direct Plan (www.hdfcfund.com)](https://www.hdfcfund.com/explore/mutual-funds/hdfc-elss-tax-saver/direct) | blocked | HTTP 403 to automated requests (re-checked 09 Nov 2026). | 2026-11-09 |
| SRC-004 | AMC | [HDFC Small Cap Fund - Direct Plan (www.hdfcfund.com)](https://www.hdfcfund.com/explore/mutual-funds/hdfc-small-cap-fund/direct) | blocked | HTTP 403 to automated requests (re-checked 09 Nov 2026). | 2026-11-09 |
| SRC-005 | AMC | [HDFC Balanced Advantage Fund - Direct Plan (www.hdfcfund.com)](https://www.hdfcfund.com/explore/mutual-funds/hdfc-balanced-advantage-fund/direct) | blocked | HTTP 403 to automated requests (re-checked 09 Nov 2026). | 2026-11-09 |
| SRC-006 | AMC | [KIM fund documents hub (www.hdfcfund.com)](https://www.hdfcfund.com/mutual-funds/fund-documents/kim) | blocked | HTTP 403 to automated requests (re-checked 09 Nov 2026). | 2026-11-09 |
| SRC-007 | AMC | [SID fund documents hub (www.hdfcfund.com)](https://www.hdfcfund.com/mutual-funds/fund-documents/sid) | blocked | HTTP 403 to automated requests (re-checked 09 Nov 2026). | 2026-11-09 |
| SRC-008 | AMC | [Statutory disclosures (www.hdfcfund.com)](https://www.hdfcfund.com/statutory-disclosure) | blocked | HTTP 403 to automated requests (re-checked 09 Nov 2026). | 2026-11-09 |
| SRC-009 | AMC | [TER of schemes - reports (www.hdfcfund.com)](https://www.hdfcfund.com/statutory-disclosure/total-expense-ratio-of-mutual-fund-schemes/reports) | blocked | HTTP 403 to automated requests (re-checked 09 Nov 2026). | 2026-11-09 |
| SRC-010 | AMC | [TER of schemes - notices (www.hdfcfund.com)](https://www.hdfcfund.com/statutory-disclosure/total-expense-ratio-of-mutual-fund-schemes/notices) | blocked | HTTP 403 to automated requests (re-checked 09 Nov 2026). | 2026-11-09 |
| SRC-013 | SEBI | [SEBI circular - Investor Charter and disclosure of investor complaints by MFs (10 Dec 2021)](https://www.sebi.gov.in/legal/circulars/dec-2021/circular-on-investor-charter-and-disclosure-of-investor-complaints-by-mutual-funds-on-their-websites-and-amfi-website-_54545.html) | excluded | PDF viewer shell - the page itself has ~440 characters; the circular text is an embedded PDF at a different URL (/sebi_data/attachdocs/dec-2021/1639140643172.pdf), which the no-link-following policy does not fetch. | 2026-11-09 |
| SRC-014 | SEBI | [SEBI circular - Categorization and Rationalization of MF Schemes (26 Feb 2026)](https://www.sebi.gov.in/legal/circulars/feb-2026/categorization-and-rationalization-of-mutual-fund-schemes_99983.html) | excluded | PDF viewer shell - the page itself has ~250 characters; the circular text is an embedded PDF at a different URL (/sebi_data/attachdocs/feb-2026/1772079826878.pdf). | 2026-11-09 |
| SRC-016 | SEBI | [SEBI Investor - Investor Education Reading Material (index)](https://investor.sebi.gov.in/iematerial.html) | excluded | Index page of links to booklets (embedded PDF viewers); no facts on the page itself. | 2026-11-09 |
| SRC-017 | AMFI | [AMFI - Investor Corner (hub)](https://www.amfiindia.com/investor) | excluded | Hub page describing AMFI's investor sections; no scheme or regulatory facts. | 2026-11-09 |
| SRC-015 | SEBI | [SEBI - Categorization and Rationalization of MF Schemes (Oct 2017)](https://www.sebi.gov.in/sebi_data/attachdocs/oct-2017/1509103633344.pdf) | historical | Superseded; AMFI's categorisation article is used instead. | - |

## Inventory reconciliation (SRC-001 ... SRC-024)

Every candidate from the original source inventory and what happened to it.

| Inventory | Candidate | Decision | In the corpus as |
|---|---|---|---|
| SRC-001 | [HDFC Large Cap Fund - Direct Plan (www.hdfcfund.com)](https://www.hdfcfund.com/explore/mutual-funds/hdfc-large-cap-fund/direct) | blocked (HTTP 403) - replaced | `hdfc_large_cap_sid` |
| SRC-002 | [HDFC Flexi Cap Fund - Direct Plan (www.hdfcfund.com)](https://www.hdfcfund.com/explore/mutual-funds/hdfc-flexi-cap-fund/direct) | blocked (HTTP 403) - replaced | `hdfc_flexi_cap_sid` |
| SRC-003 | [HDFC ELSS Tax Saver Fund - Direct Plan (www.hdfcfund.com)](https://www.hdfcfund.com/explore/mutual-funds/hdfc-elss-tax-saver/direct) | blocked (HTTP 403) - replaced | `hdfc_elss_sid` |
| SRC-004 | [HDFC Small Cap Fund - Direct Plan (www.hdfcfund.com)](https://www.hdfcfund.com/explore/mutual-funds/hdfc-small-cap-fund/direct) | blocked (HTTP 403) - replaced | `hdfc_small_cap_sid` |
| SRC-005 | [HDFC Balanced Advantage Fund - Direct Plan (www.hdfcfund.com)](https://www.hdfcfund.com/explore/mutual-funds/hdfc-balanced-advantage-fund/direct) | blocked (HTTP 403) - replaced | `hdfc_baf_sid` |
| SRC-006 | [KIM fund documents hub (www.hdfcfund.com)](https://www.hdfcfund.com/mutual-funds/fund-documents/kim) | blocked (HTTP 403) - replaced | `hdfc_common_equity_kim` |
| SRC-007 | [SID fund documents hub (www.hdfcfund.com)](https://www.hdfcfund.com/mutual-funds/fund-documents/sid) | blocked (HTTP 403) - replaced | `hdfc_large_cap_sid`, `hdfc_flexi_cap_sid`, `hdfc_elss_sid`, `hdfc_small_cap_sid`, `hdfc_baf_sid` |
| SRC-008 | [Statutory disclosures (www.hdfcfund.com)](https://www.hdfcfund.com/statutory-disclosure) | blocked (HTTP 403) - replaced | `hdfc_factsheet_sep_2026` |
| SRC-009 | [TER of schemes - reports (www.hdfcfund.com)](https://www.hdfcfund.com/statutory-disclosure/total-expense-ratio-of-mutual-fund-schemes/reports) | blocked (HTTP 403) - replaced | `hdfc_factsheet_sep_2026` |
| SRC-010 | [TER of schemes - notices (www.hdfcfund.com)](https://www.hdfcfund.com/statutory-disclosure/total-expense-ratio-of-mutual-fund-schemes/notices) | blocked (HTTP 403) - replaced | `hdfc_factsheet_sep_2026` |
| SRC-011 | [SEBI - FAQs for Mutual Fund Investors (updated as on 31 Aug 2024)](https://www.sebi.gov.in/sebi_data/faqfiles/sep-2024/1727242783639.pdf) | ingested | `sebi_mf_faq` |
| SRC-012 | [SEBI - Investor Charter](https://investor.sebi.gov.in/Investor-charter.html) | ingested | `sebi_investor_charter` |
| SRC-013 | [SEBI circular - Investor Charter and disclosure of investor complaints by MFs (10 Dec 2021)](https://www.sebi.gov.in/legal/circulars/dec-2021/circular-on-investor-charter-and-disclosure-of-investor-complaints-by-mutual-funds-on-their-websites-and-amfi-website-_54545.html) | excluded | - |
| SRC-014 | [SEBI circular - Categorization and Rationalization of MF Schemes (26 Feb 2026)](https://www.sebi.gov.in/legal/circulars/feb-2026/categorization-and-rationalization-of-mutual-fund-schemes_99983.html) | excluded | - |
| SRC-015 | [SEBI - Categorization and Rationalization of MF Schemes (Oct 2017)](https://www.sebi.gov.in/sebi_data/attachdocs/oct-2017/1509103633344.pdf) | historical - excluded | - |
| SRC-016 | [SEBI Investor - Investor Education Reading Material (index)](https://investor.sebi.gov.in/iematerial.html) | excluded | - |
| SRC-017 | [AMFI - Investor Corner (hub)](https://www.amfiindia.com/investor) | excluded | - |
| SRC-018 | [AMFI - Introduction to Mutual Funds](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=IntroductionMutualFunds) | ingested | `amfi_intro_mf` |
| SRC-019 | [AMFI - Types of Mutual Fund Schemes](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=TypesOfMutualFundSchemes) | ingested | `amfi_types` |
| SRC-020 | [AMFI - Expense Ratio](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=expenseRatio) | ingested | `amfi_expense_ratio` |
| SRC-021 | [AMFI - Net Asset Value (NAV)](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=NetAssetValueNAV) | ingested | `amfi_nav` |
| SRC-022 | [AMFI - Categorization of Mutual Fund Schemes](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=CategorizationOfMutualFundSchemes) | ingested | `amfi_categorization` |
| SRC-023 | [AMFI - Risks in Mutual Funds](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=riskInMutualFunds) | ingested | `amfi_risk` |
| SRC-024 | [AMFI - Understanding Mutual Funds (investor awareness booklet)](https://www.amfiindia.com/uploads/AMFI_Understanding_Mutual_Funds_IAP_Booklet_Final_Website_version_860a5b77aa.pdf) | ingested | `amfi_booklet` |

Of the 24 inventory entries: **9 ingested**, **10 replaced** by the same official documents on `files.hdfcfund.com`, **4 excluded** after review and **1 historical**. 4 official sources were added beyond the inventory: `hdfc_small_cap_ssd`, `hdfc_request_statement`, `hdfc_cas`, `sebi_elss`.

## Notes
- `www.hdfcfund.com` returns HTTP 403 to automated requests. HDFC's own document server `files.hdfcfund.com` does not, so scheme facts come from the official SIDs, the Common Equity KIM and the monthly factsheet there.
- Pages from `www.hdfcfund.com` marked *manual* are saved by hand into `data/manual/`; their original URL stays the citation.
- Returns, SIP-performance, risk-ratio and portfolio sections are removed from documents before anything is stored.
