# Sources

FundFacts AI uses only official public sources from **HDFC Mutual Fund (AMC), SEBI and AMFI**. **18 sources are ingested**, and each URL below is fetched exactly once per build; links inside pages are never followed. The machine-readable list is [`sources.csv`](sources.csv) and the registry is [`sources.yaml`](sources.yaml).

| # | Publisher | Type | Title | Scheme | Status | Retrieved (IST) |
|---|---|---|---|---|---|---|
| 1 | AMC | SID | [Scheme Information Document - HDFC Large Cap Fund (21 Nov 2025)](https://files.hdfcfund.com/s3fs-public/SID/2025-11/SID%20-%20HDFC%20Large%20Cap%20Fund%20dated%20November%2021,%202025.pdf) | HDFC Large Cap Fund | ingested | 09 Nov 2026 |
| 2 | AMC | SID | [Scheme Information Document - HDFC Flexi Cap Fund (21 Nov 2025)](https://files.hdfcfund.com/s3fs-public/SID/2025-11/SID%20-%20HDFC%20Flexi%20Cap%20Fund%20dated%20November%2021,%202025.pdf) | HDFC Flexi Cap Fund | ingested | 09 Nov 2026 |
| 3 | AMC | SID | [Scheme Information Document - HDFC ELSS Tax Saver Fund (21 Nov 2025)](https://files.hdfcfund.com/s3fs-public/SID/2025-11/SID%20-%20HDFC%20ELSS%20Tax%20Saver%20Fund%20dated%20November%2021,%202025.pdf) | HDFC ELSS Tax Saver Fund | ingested | 09 Nov 2026 |
| 4 | AMC | SID | [Scheme Information Document - HDFC Mid Cap Fund (21 Nov 2025)](https://files.hdfcfund.com/s3fs-public/SID/2025-11/SID%20-%20HDFC%20Mid%20Cap%20Fund%20dated%20November%2021,%202025_1.pdf) | HDFC Mid Cap Fund | ingested | 09 Nov 2026 |
| 5 | AMC | SID | [Scheme Information Document - HDFC Small Cap Fund (21 Nov 2025)](https://files.hdfcfund.com/s3fs-public/SID/2025-11/SID%20-%20HDFC%20Small%20Cap%20Fund%20dated%20November%2021,%202025.pdf) | HDFC Small Cap Fund | ingested | 09 Nov 2026 |
| 6 | AMC | KIM | [Key Information Memorandum - HDFC equity schemes (28 Nov 2025)](https://files.hdfcfund.com/s3fs-public/2025-12/Common%20Equity%20KIM%20dated%20November%2028%2C%202025.pdf) | - | ingested | 09 Nov 2026 |
| 7 | AMC | factsheet | [HDFC MF Factsheet - September 2026](https://files.hdfcfund.com/s3fs-public/2026-10/HDFC%20MF%20Factsheet%20-%20September%202026.pdf) | - | ingested | 09 Nov 2026 |
| 8 | AMFI | SSD | [Scheme Summary Document - HDFC Small Cap Fund (AMFI)](https://portal.amfiindia.com/spages/SSD_8547.pdf) | HDFC Small Cap Fund | ingested | 09 Nov 2026 |
| 9 | AMC | guide | [HDFC Mutual Fund - Request Statement (account and capital gains statements)](https://www.hdfcfund.com/services/additional-info/request-statement) | - | manual download pending | - |
| 10 | AMC | guide | [HDFC Mutual Fund - Download Consolidated Account Statement](https://www.hdfcfund.com/services/consolidated-account-statement) | - | manual download pending | - |
| 11 | SEBI | FAQ | [SEBI - FAQs for Mutual Fund Investors (updated as on 31 Aug 2024)](https://www.sebi.gov.in/sebi_data/faqfiles/sep-2024/1727242783639.pdf) | - | ingested | 09 Nov 2026 |
| 12 | SEBI | guide | [SEBI Investor - A Guide to ELSS](https://investor.sebi.gov.in/elss.html) | - | ingested | 09 Nov 2026 |
| 13 | SEBI | guide | [SEBI - Investor Charter](https://investor.sebi.gov.in/Investor-charter.html) | - | ingested | 09 Nov 2026 |
| 14 | AMFI | article | [AMFI - Introduction to Mutual Funds](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=IntroductionMutualFunds) | - | ingested | 09 Nov 2026 |
| 15 | AMFI | article | [AMFI - Types of Mutual Fund Schemes](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=TypesOfMutualFundSchemes) | - | ingested | 09 Nov 2026 |
| 16 | AMFI | article | [AMFI - Expense Ratio](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=expenseRatio) | - | ingested | 09 Nov 2026 |
| 17 | AMFI | article | [AMFI - Net Asset Value (NAV)](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=NetAssetValueNAV) | - | ingested | 09 Nov 2026 |
| 18 | AMFI | article | [AMFI - Categorization of Mutual Fund Schemes](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=CategorizationOfMutualFundSchemes) | - | ingested | 09 Nov 2026 |
| 19 | AMFI | article | [AMFI - Risks in Mutual Funds](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=riskInMutualFunds) | - | ingested | 09 Nov 2026 |
| 20 | AMFI | guide | [AMFI - Understanding Mutual Funds (investor awareness booklet)](https://www.amfiindia.com/uploads/AMFI_Understanding_Mutual_Funds_IAP_Booklet_Final_Website_version_860a5b77aa.pdf) | - | ingested | 09 Nov 2026 |
| 21 | AMC | article | [HDFC MF scheme pages on www.hdfcfund.com (all five schemes)](https://www.hdfcfund.com/explore/mutual-funds/hdfc-flexi-cap-fund/direct) | - | not ingested (blocked) | - |
| 22 | SEBI | circular | [SEBI - Categorization and Rationalization of MF Schemes (Oct 2017)](https://www.sebi.gov.in/sebi_data/attachdocs/oct-2017/1509103633344.pdf) | - | not ingested (historical) | - |

## Notes
- `www.hdfcfund.com` returns HTTP 403 to automated requests. HDFC's own document server `files.hdfcfund.com` does not, so scheme facts come from the official SIDs, the Common Equity KIM and the monthly factsheet there.
- Pages from `www.hdfcfund.com` marked *manual* are saved by hand into `data/manual/`; their original URL stays the citation.
- Returns, SIP-performance, risk-ratio and portfolio sections are removed from documents before anything is stored.
