# Project Plan: UK VAT Identifier Discovery (Zero-API-Key Architecture)

## 1. Objective & Core Constraints
Build a fully reproducible, zero-API-key Proof of Concept (PoC) pipeline and investigative benchmark to determine whether a UK company VAT registration dataset can be built from the open web.

**Critical Domain Rules:**
- **Zero External Paid/Auth APIs:** Do NOT require any API keys (no HMRC Developer Hub OAuth, no Companies House API key, no paid search APIs). Use public bulk snapshots, open public JSON endpoints (Contracts Finder, Common Crawl CDX), polite web search/discovery, and HMRC's public web checker.
- **Backwards-only verification:** HMRC's checker confirms a 9-digit VAT number and returns the registered legal name and address, NOT vice versa.
- **Zero tolerance for false positives:** A wrong VAT number attached to a company corrupts downstream joins. Every candidate VAT number MUST pass local Modulo-97 checksum validation, HMRC verification, AND fuzzy entity resolution (matching returned HMRC name + postcode against Companies House metadata).
- **Unbiased sampling:** Do NOT cherry-pick companies known to have VAT numbers. Draw a reproducible random sample ($N = 150$) from active UK companies in B2B/commercial SIC sectors (manufacturing, construction, wholesale, retail).
- **Evidence-first logging:** Log exact counts, failure reasons, dead-end source benchmarks, and latencies at every stage for `README.md`.

---

## 2. Repository Architecture
Create the following directory structure:

```text
uk-vat-discovery/
├── PLAN.md                     # This execution blueprint
├── README.md                   # Comprehensive final report (Parts 1, 2, 3, Debate Topics, Beyond UK)
├── requirements.txt            # Python dependencies
├── .gitignore                  # Ignore data/raw/*, __pycache__, .venv
├── data/
│   ├── raw/                    # Downloaded Companies House BasicCompanyData CSV (gitignored)
│   ├── sample_companies.csv    # Reproducible unbiased sample (N=150)
│   ├── candidates_extracted.csv# Checksum-valid VAT candidates found on company websites/PDFs
│   ├── hmrc_manual_queue.csv   # Optional fallback queue if HMRC web form rate-limits/blocks
│   ├── results_verified.csv    # Final PoC output with HMRC responses, match scores & audit flags
│   └── part1_source_audit.json # Quantitative benchmark results from dead-end & alternative sources
└── src/
    ├── __init__.py
    ├── config.py               # Central config, regex patterns, SIC filters, thresholds
    ├── validators.py           # UK VAT Modulo-97 checksum & EORI-to-VAT extractor
    ├── 01_sample_generator.py  # Download/stream Companies House bulk CSV & draw unbiased sample (N=150)
    ├── 02_part1_experiments.py # Benchmark alternative/dead-end sources (Contracts Finder, Common Crawl CDX, EORI)
    ├── 03_vat_extractor.py     # Domain discovery (DuckDuckGo) + async targeted crawling (/terms, /privacy, /contact, PDFs)
    ├── 04_hmrc_verifier.py     # Automated HMRC public web checker client + CSV fallback + RapidFuzz entity resolution
    └── 05_metrics_report.py    # Compute funnel metrics, false positive rate, and markdown tables for README.md
```

---

## 3. Detailed Component Specifications

### 3.1 `src/config.py`
- Target sample size: $N = 150$, Random Seed: `42`.
- Active company filters: `CompanyStatus == 'Active'`.
- Commercial / B2B SIC code ranges:
  - 10000 - 33200: Manufacturing (C)
  - 41000 - 43999: Construction (F)
  - 46000 - 46900: Wholesale trade (G46)
  - 47000 - 47999: Retail trade (G47)
  - 62000 - 62090: Computer programming & consultancy (J62)
- Exclude dormant accounts (`Accounts.AccountCategory == 'DORMANT'`).
- Regex patterns for UK VAT extraction (standard 9-digit, GB prefix, EORI GB+9digits).
- Thresholds for fuzzy matching: Name similarity ratio $\ge 0.75$, Postcode exact outward code match or normalized comparison.

### 3.2 `src/validators.py`
- UK standard VAT number consists of 9 digits.
- **Modulo 97 Algorithm:**
  - Weights: `[8, 7, 6, 5, 4, 3, 2]` for digits 1 through 7.
  - Sum $S = \sum_{i=1}^7 d_i \cdot w_i$.
  - Check digits $C = 10 \cdot d_8 + d_9$.
  - Standard check: $(S + C) \pmod{97} == 0$.
  - Post-Nov 2009 alternative rule: $(S + C + 55) \pmod{97} == 0$.
- EORI extractor: Extracts 9-digit core from `GB` + 9 digits or `GB` + 12 digits (`GB` + 9 digits + 3 zeros).

### 3.3 `src/01_sample_generator.py`
- Efficient streaming / chunked reader over the 2.8 GB `BasicCompanyDataAsOneFile.csv`.
- Filters active, non-dormant companies with designated SIC codes.
- Reservoir sampling or chunked accumulation with fixed seed (`42`) to produce `sample_companies.csv` ($N=150$).

### 3.4 `src/02_part1_experiments.py`
- Empirical investigation of alternative/dead-end sources required for Part 1:
  1. **Contracts Finder API / Open Procurement Data:** Check coverage of supplier VAT/company numbers in UK public tender releases.
  2. **Common Crawl CDX / Bulk web index:** Query CDX index for domain presence and candidate extraction feasibility.
  3. **HMRC Public EORI checker:** Check whether EORI numbers can be resolved or queried.
- Quantitatively records hits, misses, latency, and failure reasons in `data/part1_source_audit.json`.

### 3.5 `src/03_vat_extractor.py`
- Step 1: Discover company official website / domain using polite search heuristics (Company Name + Registered Town/Postcode).
- Step 2: Fetch and parse high-yield paths (`/`, `/terms`, `/privacy`, `/contact`, `/legal`, `/about`, `/imprint`).
- Step 3: Parse PDF invoices/catalogues if discovered.
- Step 4: Extract candidate VAT strings and run `validators.py` (Modulo-97). Outputs `data/candidates_extracted.csv`.

### 3.6 `src/04_hmrc_verifier.py`
- Queries HMRC's public "Check a UK VAT number" web endpoint (`https://www.tax.service.gov.uk/check-vat-number/enter-vat-details`).
- Parses returned registered name and registered address.
- Performs RapidFuzz entity resolution:
  - Compares HMRC registered name with Companies House `CompanyName`.
  - Compares HMRC address / postcode with Companies House `RegAddress.PostCode`.
- Emits verification status: `VERIFIED_MATCH`, `VERIFIED_MISMATCH` (false positive candidate caught!), `INVALID_NUMBER`, or `UNCHECKED`.
- Generates `data/results_verified.csv` and `data/hmrc_manual_queue.csv` (fallback if needed).

### 3.7 `src/05_metrics_report.py`
- Computes:
  - Total Sample ($N$)
  - Domain Discovery Rate
  - Candidate VAT Extraction Rate
  - Modulo-97 Pass Rate
  - HMRC Verification Rate
  - Entity Resolution Match Rate
  - False Positive Rate (Checksum passed but mismatched entity or invalid at HMRC)
  - Estimated UK-wide yield and cost breakdown.
- Formats tables for direct inclusion in `README.md`.
