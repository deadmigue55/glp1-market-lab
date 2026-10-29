# Model card: the GLP-1 event-driven forecast (M2)

Not investment advice. This card describes what the forecast is, what it was tested on, and where it
should not be used.

## What it is

A predictive distribution for the log return of Eli Lilly (LLY) and the Novo Nordisk ADR (NVO) at 1, 5, 21,
63, 126 and 252 trading days, published every weekday evening.

- **Diffusion:** a GJR-GARCH(1,1) with Student-t errors and zero mean, fitted since 2018 to returns whose
  news-day moves are clipped at 2.5 trailing standard deviations.
- **Jumps:** a scheduled jump at each expected earnings report (size estimated from past ledger events) and
  unscheduled jumps arriving at the historical rate with the historical size.
- **Calibration:** the width is scaled by an adaptive conformal factor learned from past misses of the same
  forecast at the same horizon (Gibbs and Candes 2021).
- **On the live page:** the visitor can replace the earnings jump with a chosen outcome (or the model's
  historical mix of guidance raised, unchanged and cut, centred at zero) and add a binary jump for the CagriSema
  FDA decision, priced from the Kalshi contract and sized from Novo's past unscheduled news days.

## Intended use

Seeing how wide the range of outcomes is, how it changes with dated events, and how the same method has
scored. Teaching, portfolio and research.

## Not for

Trading signals, position sizing, price targets, or any decision where a wrong range costs money. The model has
no direction view (zero mean by design) and no information about anything it was not told: new trial data,
policy changes, competitor results and earnings content reach it only after they are in the ledger.

## Evaluation

Rolling-origin backtest, weekly origins from 2021-01-04, development to 2025-10-31 (outcomes inside the
period only), test from 2025-11-03; scored by CRPS, coverage and Diebold-Mariano tests against a random walk,
GARCH and a filtered-historical-simulation GARCH. Results are in [forecast.md](forecast.md): no practical
CRPS gain from the jump layer, better-calibrated intervals from the conformal step.

## Known limits

- Two stocks and one extraordinary regime; few independent windows at long horizons, none out of sample at
  252 days, where the interval is very wide.
- The earnings calendar beyond the next report is projected from the last quarterly report, so dates can be
  off by one to two weeks.
- Ledger events were curated with hindsight; their count (116) limits how finely the jump sizes can be pooled.
- Foundation-model baselines and option-implied benchmarks were not run (amendments 11 and 12).
- Outcomes chosen on the page are scenarios, not predictions of those outcomes.

## Monitoring

The nightly run appends each forecast to a hash-chained public ledger (`forecasts/ledger.jsonl`) and scores
it when the horizon passes; the page shows coverage as it accumulates. A forecast whose 80% interval holds
well below 80% of the time over many windows is evidence against the model.
