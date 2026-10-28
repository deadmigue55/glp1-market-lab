# The GLP-1 catalyst ledger

A hand-curated, dated, sourced list of the news that could move GLP-1 stocks: `data/ledger/catalysts.csv`
(116 events, 2017-2026) and the forward calendar `data/ledger/forward_calendar.csv` (6 upcoming
catalysts). Licence: CC BY 4.0. Rebuild with `scripts/make_ledger.py`; check with `uv run glp1 ledger`.

## What an event is

News from a company, regulator or government that a reader could tie to GLP-1 economics. Eight types,
fixed in advance (methodology section 3): trial readout, regulatory, pricing or policy, competitor,
supply, safety, earnings or guidance, M&A or licensing.

| Type | Events |
|---|---|
| Earnings or guidance | 53 |
| Trial readout | 30 |
| Regulatory | 16 |
| M&A or licensing | 7 |
| Pricing or policy | 4 |
| Supply | 4 |
| Competitor | 1 |
| Safety | 1 |

## Columns

`event_id`, `ticker` (the issuer: NVO covers both the ADR and Novo B), `also_affects` (read-through
tickers), `event_type`, `title`, `occurred_at` (UTC), `timing`, `stated_date`, `timestamp_source`,
`source_url`, `scheduled`, `announced_on`, `surprise`, `surprise_basis`, `confounded`, `verified_on`,
`notes`.

## Timing: what `occurred_at` means

- `exact` (11 events): the time printed on the company's own release (PR Newswire pages for Lilly,
  novonordisk.com for SELECT).
- `upper_bound` (105 events): the news was public by this time. Mostly the SEC acceptance time of the
  8-K or 6-K that carried it, which follows the company's own release. `stated_date` is the release
  date printed in the text. Of the Novo 6-Ks, 55-70% were filed the same day and the rest one or more
  days later, so the event study uses day 0 only when the filing was on the stated date before the
  close, and a `[0,+1]` window otherwise (methodology amendment 2).
- Date-only events (regulators, policy) are stored as the last minute of the day, which puts them in
  the `[0,+1]` window.

For the 95 EDGAR rows, `occurred_at` matches the SEC record exactly (checked against the cached
submissions), and no stated date falls after its filing.

## Surprise: what `surprise` means

Filled from the release text before any return was looked at (amendment 3). 48 of 116 events have one.

- Weight-loss readouts: headline weight loss minus the record phase 3 headline at the time (8.0 SCALE;
  14.9 STEP 1 from 2020-06-04; 22.5 SURMOUNT-1 from 2022-04-28; 22.7 REDEFINE 1 from 2024-12-20; 28.7
  TRIUMPH-4 from 2025-12-11), in percentage points. Head-to-head trials use the active comparator.
- SELECT (the stated exception, amendment 4): MACE reduction minus LEADER's 13%.
- Earnings and outlook: change in the midpoint of the company's own full-year guidance, only where the release gives both the prior and the new range. First-time guidance carries none.
- Phase 2 readouts, approvals, policy and every other type carry none.

Every value has its rule in `surprise_basis`. Different rules are different units; the models split on
`surprise_basis`.

## Known limits

- **Coverage is deliberately uneven.** Earnings and guidance rows start in 2021 (Lilly's and Novo's
  2017-2020 reports are in the cache but outside the ledger; the GLP-1 obesity story starts with
  STEP 1 in 2020). Novo files every announcement with the SEC, so its GLP-1 news is close to complete
  from 2017; Lilly files only earnings and a few other items, so Lilly's trial and regulatory news is
  a hand-built list of ten events with exact times, not a census. Competitors are the largest ones;
  there is one safety event. Each gap is a place a result could be biased, so the event study reports
  results by source.
- **`scheduled` and `announced_on`.** Only periodic reports are scheduled. `announced_on` is the event
  date minus a notice shorter than the one observed (30 days for Novo, which publishes a yearly
  calendar; 7 for Lilly, which confirmed its Q3 2026 date 14 days ahead), so a backtest never knows a
  date earlier than the company had said it. Early releases are unscheduled: Novo's 2026-02-03 outlook
  (released a day before the report) and its 2026-08-04 raise (a pre-announcement). A blank
  `announced_on` in the forward calendar means the date is unknown and must be treated as not knowable
  before the event.
- **Surprise is mechanical.** The record-headline rule ignores what investors expected: Novo had
  publicly pointed to a higher figure for REDEFINE 1, so +0.2 understates that disappointment.
- **`confounded` is derived by rule** (`ledger.derive_confounded`): another event within one calendar
  day whose issuer is the issuer, or a read-through ticker, of this one. 44 of 116 events are flagged,
  including cross-company earnings pairs; hand flags are kept on top. Primary tables exclude them and
  report them separately.
- **Times.** Rows for Amgen, Pfizer, Hims and the regulators are date-only (last minute of the day,
  `[0,+1]` window); no timestamp was set from a price move. The Copenhagen close is fixed at 17:00 and
  half-day sessions are not modelled; no ledger event falls in one.
- **Price coverage.** WW has no price series before 2025-06-27, so its Sequence row cannot be
  studied; Akero (bought by Novo) and Metsera are not in the universe.
- **Single curator.** `verified_on` records that each row was checked against its source on that
  date. An independent read-only review (steps 1-2) found the issues now fixed here and listed in
  `docs/data.md`.

## Forward calendar

Six expected catalysts with the date each became known (`announced_on`), so the forecast can be
scored on what was knowable at the time: Lilly Q3 2026 results (2026-10-29), Novo Q3 2026 results
(2026-11-04, unconfirmed), the FDA decision on CagriSema (Q4 2026), retatrutide's FDA filing
(Q1 2027), and two policy dates on 2027-01-01.

Not investment advice.
