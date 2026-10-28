# Research notes

Facts with a source and a confidence tag. `[verified]` = read from the source on the date given.
`[probe]` = a network probe reached the endpoint, content not yet inspected. `[memory]` = recalled,
must be confirmed before use. `[to verify]` = never use a number tagged this way in a result.

## 1. State of the world (as of 2026-10-27)

| Fact | Source | Tag |
|---|---|---|
| Lilly near all-time high, ~$1,295 on 2026-10-20 after a positive EU committee opinion for oral Foundayo (orforglipron) | 24/7 Wall St, 2026-10-20 | secondary, to verify against Lilly and EMA releases |
| Lilly 2026 revenue outlook up to $87bn (vs $65bn in 2025) | Yahoo Finance / Motley Fool | secondary, to verify in the Q2 10-Q |
| FDA approved orforglipron (Foundayo) in the US on 2026-04-01 | tracker sites | to verify against Drugs@FDA |
| Novo guidance: adjusted sales growth 0% to -6% at constant FX, US sales decline | Novo 6-K filed on SEC EDGAR | primary, to verify when the ledger is built |
| CagriSema REDEFINE-4 failed non-inferiority against tirzepatide (20.2% vs 23.6%), 2026-02-23 | tracker sites | to verify against the Novo release |
| CagriSema US decision expected Q4 2026; Novo plans a 2027 launch if approved | tracker sites | to verify |
| Retatrutide US filing planned Q1 2027 | tracker sites | to verify against Lilly's release |
| Kalshi lists FDA-approval contracts for CagriSema (series `KXFDAAPPROVE-CAG-*`); a May 2026 snapshot priced approval before 2028 at 81% | simplefunctions.dev aggregator | secondary; read Kalshi's own API in step 8 |

The secondary sources disagree in places (one reported Lilly -5% to $937 on an FDA decision, which does
not match the October price). Every number above is re-read from a primary source when the catalyst
ledger is built (step 2). None of them is used in a result before that.

## 2. Data sources: probe results (2026-10-27, `uv run glp1 doctor`)

| Source | Use | Result | Notes |
|---|---|---|---|
| Yahoo Finance chart API | prices, 60-minute bars | HTTP 200 | unofficial; cache raw responses; cross-check against Stooq |
| Stooq CSV | fallback daily prices | HTTP 200 | |
| Ken French Data Library | daily factors (FF5, momentum) | HTTP 200 | zip download |
| SEC EDGAR (`data.sec.gov`) | filing acceptance timestamps, XBRL facts | HTTP 200 with identification | requires `SEC_USER_AGENT` ("Name email") |
| ClinicalTrials.gov API v2 | trial registry, dates | HTTP 200 | |
| openFDA | approvals, labels | HTTP 200 | |
| Wikimedia pageviews | public attention | HTTP 200 with a descriptive User-Agent | 403 without one |
| Kalshi public market data | market-implied approval odds | HTTP 200 | read-only public endpoint |
| GDELT DOC 2.0 | news volume and tone | **HTTP 429** from this machine, repeatedly, spaced 7 s apart | treated as optional. No workaround was attempted. Retry later with an honest User-Agent; news coverage otherwise comes from company releases and EDGAR 8-K/6-K filings, which are the primary record anyway |

Options history is not free anywhere reliable, so a nightly job snapshots option chains from step 8 on.
That archive starts late, and every result that uses it says so.

## 3. Job-listing recon (OpenJobs, 2026-10-27)

Three postings read in full (Bank of America Quantitative Finance Analyst, Capital One Model Risk Office
data scientist, TransUnion data scientist) plus titles from three searches. The sample is small and
US/Chicago-heavy, so this is a hint, not a measurement.

Recurring requirements: Python, R, SQL; statistical modelling; time series; "building, validating and
backtesting" models; model documentation and model risk / model validation; stress testing and
scenario analysis (CCAR, CECL named); large datasets (Spark, Hive); machine learning (gradient boosted
trees, survival analysis, sentiment analysis, PCA); LLM tooling (PyTorch, Hugging Face, LangChain);
communicating results to executives. Many ask for a master's degree.

How the project answers: backtested forecasts under a fixed protocol; a model card and a validation
report; scenario analysis as the product; DuckDB for the data layer; an NLP step with a leakage test;
plain-English panels for non-specialists.

## 4. Sources still to read in full (step 2 onward)

- MacKinlay (1997), *Event Studies in Economics and Finance*; Boehmer, Musumeci and Poulsen (1991);
  Kolari and Pynnönen (2010).
- Arkhangelsky et al. (2021), *Synthetic Difference-in-Differences*.
- Diebold and Yilmaz (2012); Antonakakis, Gabauer and Gupta (2020) for TVP-VAR connectedness.
- Gibbs and Candès (2021), *Adaptive Conformal Inference Under Distribution Shift*.
- Diebold and Mariano (1995); Harvey, Leybourne and Newbold (1997).
- Gneiting and Raftery (2007) for proper scoring rules.
- Glasserman and Lin (2023) for look-ahead bias in language models.
- Phase-transition success rates for drug development (BIO/Informa/QLS); exact edition and figures to be
  read and recorded before use.
