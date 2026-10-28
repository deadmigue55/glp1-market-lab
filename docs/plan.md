# Weight of News: how GLP-1 drugs reprice pharma, and a forecast that updates with the news

## Context

Third flagship for the portfolio (after Mortality Table Builder and FinCrime Lab), meant to be the best yet. The goal is to get the user (risk analyst intern at SCOR, Exam FM on 2026-12-11) into quant, data science, risk, fintech or insurtech roles. There are two readers:
- **The glancer** (recruiter): a topic everyone recognises (GLP-1s) and the keywords job listings ask for.
- **The deep reader** (hiring manager): methods that hold up under scrutiny, with every newer method justified against the industry standard in a fair test.

The user set the baseline: (1) how GLP-1s affected the stocks, the market and the industry, and how big that effect is in numbers; (2) how to forecast prices when the news is volatile but mostly promising; (3) how to update the forecast as news arrives. The finished thing is **both a live scenario page (the main attraction) and a written study**. There is no deadline, and the user handed over all tool and method choices ("just do your best", work autonomously, no permission prompts).

The state of the world as of 2026-10-27 shapes the design:
- Lilly is near all-time highs (around $1,295), guides up to $87bn 2026 revenue, and its oral Foundayo (orforglipron) was approved in the US on 2026-04-01 and has a positive EU opinion.
- Novo guides 0 to -6% sales growth. CagriSema failed head-to-head non-inferiority against tirzepatide (REDEFINE-4, Feb 2026), and its FDA decision is expected in Q4 2026. Kalshi trades contracts on that decision (KXFDAAPPROVE-CAG-*).
- Retatrutide is expected to be filed in Q1 2027.

So there are live, dated catalysts that the forecast can be scored against in public.

## Decisions (my calls, stated once)

- **Repo:** new public repo `deadmigue55/glp1-market-lab`, local `C:\Users\migue\projects\glp1-market-lab`, package `glp1`, CLI `uv run glp1 ...`. Same conventions as fincrime-lab: uv, Python 3.12, ruff, pytest, pre-commit, CI, `doctor` command, DuckDB warehouse, Polars.
- **Data:** free and public only, so anyone can rerun it. The raw cache is gitignored and only aggregates are published.
- **Live page:** a static React + Vite app on **GitHub Pages**, not Vercel. The nightly GitHub Action commits are authored by a bot, and Vercel Hobby blocks deploys whose HEAD commit is not by Miguel (the lesson from Reactivo). The simulation runs in the browser in a Web Worker, as a JS port verified against Python, the same pattern as the portfolio mortality explorer.
- **Written study:** a Quarto report generated from the results JSON, the same pattern as `fincrime/site.py`, plus methodology docs.
- **Language:** English only for v1.
- **LLMs:** local-first, with no paid API needed. A Claude API path is optional if a key is present.
- **Rigor:** the evaluation protocol is fixed before any test data is touched, with numbered amendments. Each step ends with an independent read-only subagent review, which found real bugs in every FinCrime step. Every published number is tied to results JSON by a ledger test.
- **Commits:** no Claude co-author trailers (memory rule overrides the harness reminder). Push as I go.
- **Disclaimer:** "Not investment advice" everywhere. The page never gives buy or sell signals. It forecasts the **size and shape of uncertainty and how news shifts it**, not direction.

## Universe

- **Makers and challengers:** LLY, NVO (plus NOVO-B.CO as a cross-check), AMGN (MariTide), VKTX, ZEAL.CO (Zealand), PFE (Metsera), RHHBY (Roche/Carmot), GPCR.
- **Supply-chain winners:** WST, TMO, HIMS (compounding). Catalent is included until its delisting so survivorship is handled.
- **Perceived losers:** DXCM, PODD, RMD, INSP, DVA, ISRG, ZBH, MDLZ, HSY, PEP, CAG. WW is kept with its history through bankruptcy to avoid survivorship bias.
- **Controls and benchmarks:** SPY, XLV, XPH, IHE, the S&P 500 constituents (for GLP-1 betas), Fama-French 5 factors + momentum (US, plus Europe for Novo), and DKK/USD.

## Data sources (free)

- **Prices:** yfinance, with a Stooq fallback and cross-checks (ADR vs local listing, split and dividend sanity). 60-minute bars cover the last ~2 years to time the reaction to recent events.
- **Factors:** Ken French Data Library (daily).
- **Catalyst ledger (hand-curated, the core dataset):**
  - Company press releases, FDA (Drugs@FDA and openFDA), ClinicalTrials.gov API v2, and SEC EDGAR filing **acceptance timestamps**, which give before or after market timing.
  - About 120 to 150 events from 2017 to 2026, each with a timestamp, a type from a fixed taxonomy (trial readout, regulatory, pricing/policy, competitor, supply, safety, earnings/guidance, M&A) and a source URL.
  - A forward catalyst calendar.
  - Published as a CC-BY dataset; it is a portfolio asset in itself.
- **Fundamentals:**
  - SEC EDGAR XBRL companyfacts (Lilly revenue by product) and Novo quarterly sales by product from its company announcements.
  - Real prescription volume from Medicaid State Drug Utilization Data and CMS Part D spending.
  - CDC/NHANES and WHO obesity prevalence for the patient model.
- **News and attention:** the GDELT DOC 2.0 API (article volume and tone) and Wikipedia pageviews. Google Trends is optional because it is fragile.
- **Market-implied probabilities:**
  - Kalshi public market data (FDA approval contracts).
  - Phase-transition base rates from BIO/Informa clinical success rates, as a named assumption with its source.
- **Options:** there is no free history, so a nightly Action snapshots option chains **starting now**. That builds a forward archive for implied moves around catalysts and the risk-neutral density. Limits are stated honestly.

## Methods: each newer method is paired with the standard it must beat

| Question | Industry standard (baseline) | Newer method used, and why |
|---|---|---|
| How much did each piece of news move the stock? | Market-model event study, CAR, t-test (MacKinlay 1997) | Fama-French 5 + momentum model. BMP and Kolari-Pynnönen tests, because the events cluster on the same dates for every GLP-1 stock and plain t-tests over-reject. Wild bootstrap. Intraday timing for recent events. |
| Does the size of the surprise matter? | Average CAR by event type | **Hierarchical Bayesian model (PyMC)**: abnormal return depends on event type × company × surprise (for example, weight loss vs the prior benchmark trial). Partial pooling, because there are few events per type. It feeds the jump sizes for the forecast. |
| Did losers like medtech and snacks get re-rated permanently? | Basket event study | **Synthetic difference-in-differences** (Arkhangelsky et al. 2021), cross-checked against the R `synthdid` package. It gives a counterfactual path for persistent re-ratings, such as the October 2023 "GLP-1 panic". |
| How do shocks spread across the ecosystem? | Correlation matrices | **TVP-VAR connectedness** (Diebold-Yilmaz / Antonakakis), cross-checked against R `ConnectednessApproach`: who transmits shocks, over time. |
| Which stocks carry GLP-1 risk? | Sector labels | A tradable **GLP-1 factor** (makers minus losers, with a PCA check) and a GLP-1 beta for every S&P 500 stock, plus out-of-sample stability. |
| How much of market cap is GLP-1 expectations? | DCF and sum-of-the-parts | Patient-based forecast (the pharma industry funnel) as a Monte Carlo, plus rNPV for the pipeline. Then a **reverse DCF giving the market-implied peak GLP-1 sales as a daily time series**: how expectations ballooned in 2023-24 and how Novo's collapsed in 2025. An event-day attribution answers "X% of Lilly's gain arrived on N GLP-1 news days". |
| What is the news saying? | Keyword counts and dictionary sentiment | FinBERT tone vs an embedding classifier trained on the ledger taxonomy, with an optional LLM. A **look-ahead-bias test** (date-masked text, after Glasserman & Lin) is run before any LLM output is trusted. |
| Forecast distribution | Random walk, GJR-GARCH-t, historical simulation | **Event-driven jump-diffusion**: GARCH volatility plus scheduled jumps from the catalyst calendar (outcome probabilities × hierarchical jump sizes) plus unscheduled policy and competitor jumps (compound Poisson). Calibrated with **adaptive conformal inference** (Gibbs & Candès 2021), because GARCH intervals miss under regime shifts. A foundation-model baseline (Chronos-Bolt / TimesFM) is tested honestly and reported even if it loses. |
| Updating with news | Analysts revise targets by hand | Bayes updates: a catalyst that resolves conditions the paths; outcome probabilities update from Kalshi and base rates; classified news shifts the implied-fundamentals state. A **public forecast ledger**: every nightly forecast is frozen, hashed, committed, and scored later. |

**Evaluation:**
- Rolling-origin backtest from 2018 to 2026, with the last 12 months held out and touched once.
- Metrics: CRPS, log score, pinball loss, interval coverage, and Diebold-Mariano tests.
- A separate scorecard for catalyst days (does the jump model beat GARCH where it matters?).
- Option-implied moves serve as the market's own benchmark once the archive exists.

## Steps (one or more commits each, tests and docs in every step, independent review at the end of each)

0. **Research and protocol.**
   - docs/plan.md, docs/research.md (sources with confidence tags) and docs/methodology.md (protocol fixed first).
   - Keyword recon on real job listings with the OpenJobs MCP, to confirm the glancer keywords.
   - Scaffold, CI and `glp1 doctor`.
   - The user creates the GitHub repo if `gh repo create` is denied.
1. **Data platform.**
   - Ingest prices, factors and FX into DuckDB.
   - The universe includes delisted names.
   - Data contracts and checks, a raw cache, and `glp1 ingest|check`.
2. **Catalyst ledger.**
   - Curate past events with exact timestamps.
   - A second-pass verification of every row against its source.
   - The forward calendar, published as a dataset with a datasheet.
3. **Event study.**
   - Factor models, robust tests, intraday timing.
   - Surprise regression, the hierarchical jump-size model, and post-event drift (is the market efficient on GLP-1 news?).
4. **Ecosystem.**
   - Winner and loser baskets, the GLP-1 factor, and S&P 500 GLP-1 betas.
   - SDID on the major shocks, and TVP-VAR connectedness.
   - R cross-checks.
5. **Fundamentals and valuation.**
   - Product revenue history and Medicaid volumes.
   - The patient-funnel Monte Carlo, rNPV and WACC.
   - The daily reverse-DCF market-implied peak sales, with WACC and terminal-value bands.
6. **News and attention.**
   - GDELT and pageviews.
   - The classifier comparison and the look-ahead test.
   - Does attention predict volatility?
7. **Forecast engine.**
   - Baselines, the jump-diffusion, conformal calibration and the foundation-model baseline.
   - Backtest under the protocol.
8. **Updating machinery.**
   - Bayes updates and Kalshi ingest.
   - A nightly GitHub Action: fetch, refit the light parts, write JSON, append to the forecast ledger, snapshot option chains.
9. **Live scenario app (main attraction).**
   - Pick a company and see a 12-month fan chart.
   - A catalyst timeline where each event can be toggled (approve / delay / reject, strong / in-line / weak) with probability sliders that default to model and Kalshi values.
   - A waterfall showing what moved the forecast.
   - A "news since last update" feed with each item's effect.
   - An event explorer (CAR charts) and a GLP-1 beta map.
   - A market-implied peak-sales gauge with a reverse-DCF slider, and the forecast-ledger scorecard.
   - A plain-English lead on every panel for non-finance readers.
   - The JS Monte Carlo in a Web Worker, verified against Python to a set tolerance.
   - Playwright QA and axe accessibility checks, both themes.
10. **Written study and governance.**
    - The Quarto report from the results JSON.
    - Methodology chapters, a model card, a self-validation report with a findings register, and a limitations section.
    - Ledger tests that keep numbers in docs equal to the results JSON.
11. **Release and portfolio.**
    - README with headline charts, v1.0.0 and a GitHub release.
    - A third portfolio flagship card via the generic `Flagship({cfg, copyKey})` in `portfolio/src/components/Projects.jsx` (new cfg plus `projects.<key>` copy in `src/i18n/en.js` / `es.js`, screenshots in `public/img/`, qa.py checks).
    - Swap the matching skill-chip `eg` placeholders for `proof`.

## Reuse from existing projects

- **fincrime-lab:**
  - CLI/doctor/CI scaffold, `site.py` (results JSON → Quarto report → GitHub Pages).
  - The governance ledger test pattern (tests/test_governance.py).
  - Protocol-first methodology with amendments.
- **Mortality-Table-Builder:**
  - R cross-checks via `config.find_rscript` (R 4.6.1 at `C:\Program Files\R\R-4.6.1`).
  - The figure helpers (`_headline`, `_keep_clear`).
  - Docs-site checks and the keep-alive approach.
- **portfolio:**
  - The JS-vs-Python verification approach (scripts/verify-actuarial.mjs).
  - The qa.py Playwright pattern.
  - The Flagship card.
- **Known tool lessons:**
  - Use `.venv/Scripts/*.exe` while the CLI runs.
  - Use the Write/Edit tools instead of heredocs.
  - `python -I`.
  - Never name scratch files after stdlib modules.
  - Re-add after ruff-format pre-commit edits.

## Risks and how they are handled

- **Free data breaks** (yfinance): cache raw data, Stooq fallback, checksums, and a doctor that tests every source.
- **Few events:** hierarchical pooling, and intervals reported everywhere.
- **Look-ahead bias:** event timestamps come from EDGAR acceptance times, the LLM gets the masked-date test, and point-in-time fundamentals are used.
- **Survivorship:** delisted names are kept.
- **Reverse DCF is sensitive to WACC and terminal value:** always shown as bands, never as a single number.
- **Over-claiming:** every newer method is published with its head-to-head result against the baseline, including losses.
- **Exam:** the work runs autonomously. The user is only needed for repo creation if it is blocked, and optionally an API key.

## Verification

- `uv run glp1 doctor` (every source reachable, DuckDB OK) and `uv run pytest` (unit, property and ledger tests). Ruff and pre-commit stay clean, and CI is green on every push.
- **Cross-checks:**
  - Event-study CARs against a hand-computed toy case.
  - GARCH against R `rugarch`, SDID against R `synthdid`, connectedness against R `ConnectednessApproach`.
  - The JS simulator against Python on fixed seeds to a set tolerance.
- **Planted-truth checks:**
  - Simulate prices with known jumps and verify the event study and the jump model recover them.
  - Simulate miscalibration and verify conformal coverage restores the nominal level.
- **Backtest:** run under the frozen protocol, then the test period is touched once.
- **Live app:** Playwright QA (render, scenario toggles change the fan, both themes, mobile width, axe 0 violations), then checked live on GitHub Pages.
- **Nightly Action:** a dry run, then the first real run produces a ledger entry that appears on the page.
- **Independent read-only subagent review** at the end of each step; findings are fixed or recorded as amendments.
