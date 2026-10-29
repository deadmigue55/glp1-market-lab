# The nightly forecast and the public ledger

Not investment advice. These are forecasts of the spread of a stock's move, not of its direction.
Code: `nightly.py`, `kalshi.py`. Workflow: `.github/workflows/nightly.yml`. Protocol: `methodology.md`
section 7 and amendment 12.

## What runs

Every weekday at 22:30 UTC (after the US close in summer and winter time) a GitHub Action runs
`glp1 nightly`:

1. **Fresh prices.** Daily bars for LLY and NVO are fetched from Yahoo's public chart endpoint. A bar for
   the current session is dropped until 16:30 New York time, because Yahoo serves it unfinished while the
   market is open.
2. **Scoring.** Every ledger entry whose horizon has now completed is scored (CRPS, 80% and 90% coverage)
   and its outcome is fed once to the conformal calibrator (`forecasts/scored.json` records which).
3. **Forecast.** M1 (GARCH on news-clipped returns, plus earnings jumps and unscheduled jumps estimated
   from ledger events that closed before today) at 1, 5, 21, 63, 126 and 252 trading days, widened by the
   current conformal factor to give M2. The next earnings date comes from the forward calendar when it is
   known, instead of the 91-day projection used in the backtest.
4. **Catalysts.** Upcoming dated events from the forward calendar. For an earnings report: the share of
   past reports with guidance raised, unchanged or cut, and the mean and spread of the three-day abnormal
   return in each. For the CagriSema FDA decision: the Kalshi contract price as the market's probability
   of approval (midpoint of bid and ask when the spread is at most 15 cents, else the last trade).
5. **Publish.** `site/public/data/forecast.json` and `scorecard.json` for the live page; one line appended
   to `forecasts/ledger.jsonl`; the Action commits them as a bot.

## The public ledger

Each line holds the forecast quantiles (M1, the conformal factor used, and M2), the spot price and the
timestamp, plus the SHA-256 of the previous line. Changing or deleting any past line breaks every hash
after it, and `glp1 nightly` exits with an error when the chain does not verify. A forecast for a given
stock and origin date is written once and never replaced. The git history of the repository is a second,
independent record. This is a commitment device, not a cryptographic proof: the repository owner could
rewrite history, but not without leaving the public commits as evidence.

## How the conformal state starts

`glp1 nightly --seed` replays the backtest and stores the calibrators as they stood at the last date
(`forecasts/aci_state.json`); the nightly run then carries them forward from live outcomes only. At 252
days the factor is above 2 (the backtest saw few independent windows that long), so the long-horizon fan
is very wide; the page shows it with a warning and uses 126 days as its default.

## Gaps

- **No option-chain archive.** Yahoo's option endpoint needs a session crumb that this project does not
  obtain, so implied moves are not archived and cannot yet serve as a benchmark.
- **One scheduled-date source.** Earnings dates beyond the next one are projected, and Novo's next date is
  a window rather than a confirmed day.
- **Two stocks, one model.** The ledger scores M2 only; baselines are not archived nightly.
