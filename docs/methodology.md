# Methodology and evaluation protocol

Fixed on 2026-10-27, before any price, factor or event data has been loaded. Changes are made only
through the amendment log at the end: what changed, why, and what had already been seen.

## 1. Rules of the game

1. The protocol comes first. Models, metrics, splits and decision rules are written here before any
   result exists. If a result looks wrong, it is investigated, never tuned away.
2. A newer method earns its place only by beating the standard method in a fair test under this
   protocol. A loss is published like a win.
3. The test period is touched once. Selection uses the development period only.
4. Every number in the docs and on the page comes from a results JSON file, and a test checks it.
5. The project forecasts the **size and shape of uncertainty and how news moves it**. It does not
   issue buy or sell signals. Every public surface says "not investment advice".

## 2. Time and information

- **Data window:** 2017-01-02 to the freeze date (set in step 1, recorded in the manifest).
- **Event timing.** An event is timestamped to the minute from its primary source (company release,
  EDGAR acceptance time, FDA letter). If the timestamp is before the 16:00 New York close, day 0 is that
  trading day; otherwise it is the next trading day. For Novo's Copenhagen listing the same rule uses the
  Copenhagen close, and the ADR is analysed on the New York calendar.
- **Point-in-time.** A forecast made at origin `o` may use only what was public at `o`. In particular:
  fundamentals are indexed by filing date, not period end; the scheduled-catalyst calendar carries an
  `announced_on` date, and a scheduled event enters a backtest forecast only if `announced_on <= o`;
  prices are total-return adjusted using only corporate actions known at `o`.
- **Survivorship.** Delisted and acquired names stay in the universe with their history.

## 3. Event study

- **Taxonomy** (fixed): trial readout, regulatory decision, pricing or policy, competitor event, supply
  or capacity, safety, earnings or guidance, M&A or licensing. Each event also carries a signed
  *surprise* field filled from the primary source before any return is looked at (for example, weight
  loss versus the prior benchmark trial), or left empty.
- **Windows.** Estimation window `[-250, -30]` trading days; gap of 30 days; event windows `[0,0]`,
  `[-1,+1]`, `[0,+5]`, `[0,+20]`. The primary quantity is the cumulative abnormal return over `[-1,+1]`.
- **Models.** Baseline: market model on SPY (MacKinlay). Main: Fama-French five factors plus momentum.
  Sector-adjusted variants (XLV, XPH) are sensitivity checks.
- **Tests.** The baseline test is the plain cross-sectional t-test. The main tests are
  Boehmer-Musumeci-Poulsen and Kolari-Pynnönen (which corrects for events that share dates), plus a wild
  bootstrap. Results are reported with the baseline test next to the robust ones so the reader can see
  where they disagree.
- **Confounded events** (earnings or another major release in `[-1,+1]`) are excluded from the primary
  table and kept in a sensitivity table.
- **Multiple testing.** Benjamini-Hochberg at 10% across event type × company cells. The number of
  cells tested is reported.
- **Pre-stated hypotheses** (directions are expectations, and any of them may fail):
  H1 a sponsor's trial result better than the prior benchmark raises its price; H2 a negative result for
  one leader raises the other; H3 adverse pricing or policy news lowers the makers; H4 the first
  large GLP-1 readouts re-rated medtech and food names down, and the re-rating persisted past 60 days;
  H5 the market does not drift after the news (post-event CAR `[+2,+20]` is zero).

## 4. Ecosystem

- Synthetic difference-in-differences runs only on shock dates that are already in the verified ledger
  before the method is run. Donor pool: S&P 500 names with no GLP-1 exposure in their filings. The R
  `synthdid` package is the cross-check, and the two must agree on the point estimate.
- TVP-VAR connectedness uses daily returns of the universe baskets, with the R `ConnectednessApproach`
  package as the cross-check.
- The GLP-1 factor is makers minus perceived losers. Betas are estimated on a rolling window and checked
  for out-of-sample stability against the next window.

## 5. Valuation

- The patient-funnel and reverse-DCF models list every assumption by name with a source or a rationale.
- Reverse-DCF output is a band over a fixed grid, WACC 6% to 10% and terminal growth 0% to 3%, never one
  number.
- Pipeline value uses rNPV with phase-transition rates from a named published edition (step 5 records it).

## 6. Forecast evaluation

- **Targets:** log return of each universe name at horizons of 1, 5, 21, 63, 126 and 252 trading days.
- **Development period:** origins every week from 2021-01-04 to 2025-10-31. Training data start 2018-01-02
  and are expanding.
- **Test period:** origins from 2025-11-03 to the freeze date, never examined before the candidate models
  are final.
- **Models** (the list is closed):
  B0 random walk with trailing 252-day volatility; B1 GJR-GARCH(1,1) with Student-t errors; B2 filtered
  historical simulation; B3 Chronos-Bolt zero-shot; M1 jump-diffusion (GARCH volatility, scheduled jumps
  from the point-in-time calendar, compound-Poisson unscheduled jumps); M2 M1 with adaptive conformal
  calibration. At most six configurations of M1 are tried, all on the development period.
- **Scores:** CRPS from 99 quantile levels (primary), pinball loss at 5/25/50/75/95%, coverage of the
  50/80/90% intervals, log score where a density exists.
- **Primary comparison:** mean CRPS at horizons 21 and 63 for LLY and NVO, development then test.
  Secondary: all names, all horizons, and the subset of origins within 21 trading days before a scheduled
  catalyst.
- **Decision rule:** a method beats the best baseline if its mean CRPS is lower in development and a
  one-sided Diebold-Mariano test with a Newey-West variance and the Harvey correction gives p < 0.10,
  and the sign holds in the test period. Overlapping horizons are handled with a variance bandwidth of
  at least `h - 1`. Otherwise the result is reported as "no demonstrated gain".
- **Option-implied moves** become a benchmark only once at least 60 trading days of archived chains
  exist, and the result says how many there were.

## 7. Updating and the forecast ledger

- Every nightly run freezes its forecasts, hashes the file and commits it. A forecast is scored only
  after its horizon has passed. The scorecard on the page uses the same scores as section 6.
- A probability that comes from a market (Kalshi) is shown next to the model's own base-rate figure.
  When they differ the page says so; it does not hide either.

## 8. Language models and text

- Any language model output used as a feature first passes a look-ahead test: the same text with dates
  and company names masked must give the same label at the original rate, otherwise the model has
  memory of the outcome and its output is not used for a date in its training period.
- Classifier comparison (dictionary, FinBERT, embeddings) is scored on a hand-labelled subset of the
  catalyst ledger with the labels written before the models run.

## 9. Planted-truth checks (in the test suite)

- Simulate returns with known jumps on known dates; the event study must recover them within its
  confidence interval at the stated rate.
- Simulate a miscalibrated forecaster; conformal calibration must restore coverage within 2 points.
- Simulate a panel with a known persistent re-rating; SDID must recover it and the plain basket event
  study must be shown to miss it when the donor pool drifts.

## 10. Amendment log

| # | Date | Change | Why | What had been seen |
|---|---|---|---|---|
| 1 | 2026-10-27 | Section 3: an event whose window `[-1,+1]` reaches past the last date of the Fama-French file (published with a lag of about a month) is analysed with the market-model baseline only and marked as such. | The factor files end 2026-09-30 while prices run to 2026-10-28, so the main model cannot cover the most recent events. | Row counts and last dates of the downloaded files only; no returns or events. |
| 2 | 2026-10-28 | Section 3: every ledger event carries `timing` (`exact` or `upper_bound`) and `stated_date`. An `upper_bound` event has day 0 = the stated date's first trading day only when it was filed on that date before the close; otherwise day 0 is that day or the next, and the window is analysed from `[0,+1]`. | Novo's 6-Ks reach EDGAR after the company's own release: 55-70% on the same day, the rest one or more days later (the 2023-10-13 outlook raise was filed 2023-10-16). Acceptance time is a bound, not the release time. | The filing and release dates of every Novo 6-K, and the ledger rows; no returns. |
| 3 | 2026-10-28 | Section 3: the surprise field is coded by two fixed rules, both from the source document. Weight-loss readouts: headline weight loss (pp) minus the record phase 3 headline at the time. Earnings and outlook: change in the midpoint of the company's own full-year guidance (% for Lilly's revenue range, pp for Novo's sales-growth range at CER). Other events carry no surprise. | The protocol said "filled from the primary source" without saying how; a rule written before any return is looked at keeps the hierarchical model's covariate free of hindsight. | The release texts only; no returns. |
| 4 | 2026-10-28 | Section 3: amendment 3 gains two stated exceptions (SELECT is coded against LEADER; head-to-head trials against their comparator) and `confounded` is derived by rule (another event within one calendar day whose issuer is the issuer or a read-through ticker) instead of by hand. `announced_on` for periodic reports is the event date minus a notice shorter than the observed one. Timestamps for events whose only evidence is press coverage of a price move are stored date-only. | Found by the independent review of steps 1-2: the previous-report convention gave Lilly dates months early, hand flags were inconsistent, and four times had been inferred from price reactions. | The review report and the ledger text; no returns were computed. |
| 5 | 2026-10-28 | Section 2: the freeze date is 2026-10-27, the last full session. `FREEZE_DATE` in `config.py` cuts later bars when the warehouse is built. Prices were re-fetched on 2026-10-28 before the freeze; the factor files end 2026-09-30 (amendment 1). | Section 2 required a freeze date and none had been set; the 2026-10-28 session was still open at fetch time, so its bar is partial. | Row counts and last dates only; no returns or events. |
