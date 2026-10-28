# Data platform (step 1)

`uv run glp1 ingest` downloads into `data/raw/` (gitignored, every fetch logged in `MANIFEST.csv` with
URL, time, size and SHA-256). `uv run glp1 build` rebuilds `data/glp1.duckdb` from that cache with no
network. `uv run glp1 check` runs the data contracts. Prices are daily from 2017-01-02; the last bar is 2026-10-28 for the FX series, 2026-10-27 for most US equities and 2026-10-26 for NOVO-B.CO and ZEAL.CO (the latest ingest ran before those sessions were final). The cache is not frozen yet: `ingest` overwrites the raw files in place, so a freeze date is set when step 3 starts.

## Tables

| Table | Content |
|---|---|
| `securities` | the 31-series universe (`src/glp1/universe.py`): role, currency, first date we want, notes, and whether it was downloaded |
| `prices` | open, high, low, close, adjusted close, volume; dated in the exchange's own time zone |
| `eligible_prices` | view of `prices` from each security's real listing date. **Analysis reads this view**, so SPAC-shell history (HIMS before 2021) never enters a result |
| `actions` | dividends and splits |
| `factors` | Fama-French five factors and momentum, daily, as decimals |

## What the checks found on the first full run

- 29 of 31 series downloaded. **Missing:** Metsera (MTSR, acquired by Pfizer) and Catalent (CTLT, acquired
  by Novo Holdings): Yahoo has no history for delisted tickers. WW International's series starts
  2025-06-27, the new entity after bankruptcy. This is the survivorship gap described in
  `docs/research.md`; it is reported by `glp1 check` every time, not hidden.
- SPY and the Fama-French market return agree at a daily correlation of 0.9947 over 2,448 days.
- Novo's New York line times DKK per USD matches its Copenhagen price within a median 0.45% over 2,384
  days.
- The adjusted close only moves on dividend and split days. No duplicate bars, no impossible prices, no
  US-listed series missing more than 1% of trading days.
- The factor files end 2026-09-30, 27 days before the last price. Events after that date use the
  market-model fallback (methodology, amendment 1).
- One-day moves above 30% without a split are listed for the event study (VKTX 7, ZEAL.CO 3, GPCR 3, HIMS 2,
  INSP 2, DXCM 2, WST 1, DVA 1). WST's single case is the 2025-02-13 guidance cut.

## Traps found on the way (kept as tests or checks)

- Yahoo's `range=max` silently returns a downsampled series (LLY: 169 bars instead of about 2,470).
  Requests always pass explicit `period1`/`period2`.
- Stooq answers HTTP 200 with a JavaScript bot challenge instead of CSV. It is not used, and the doctor
  now checks the response body, not only the status.
- GDELT answers HTTP 429 from this machine. Optional; see `docs/research.md`.
- A join between prices and the dividend table multiplied a count by the number of dividends; the check
  now uses `not exists`.
- DuckDB `corr` returns NaN for a constant series, and `NaN < x` is false in Python, so the cross-checks
  test `not value >= threshold`.

## Review of steps 1-2 (2026-10-28)

An independent read-only review found no defect in the day-0 and window logic and these fixes in the
rest, all applied: a Novo dateline regex miss (SUSTAIN 7 had the filing date, not the release date);
Lilly's `announced_on` convention (now a notice shorter than the observed one); `confounded` applied by
hand and inconsistently (now derived by rule); four timestamps set from press coverage of price moves
(now date-only); two Novo 2021 reports missing; amendment 3 not matching the data (amendment 4); a
validator that did not check event ids against dates or the surprise rule; a test of the eligibility
view that would have passed without the view; docs numbers not tied to the data (now a test). Open:
the quality checks read `prices`, not `eligible_prices`, so a pre-listing shell series can still
appear in their counts; a partial bar for "today" is not guarded against.
