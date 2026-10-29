# Weight of News: what GLP-1 drugs did to pharma stocks, and how far a forecast can follow the news

Not investment advice. Everything here describes the past or the spread of possible futures; nothing
recommends buying or selling anything. The live page is at
<https://deadmigue55.github.io/glp1-market-lab/>. Every finding has an ID (F1 to F13) and a row in the
[findings register](findings.md) that says how strong it is and which file and test back it.

## The question

Semaglutide (Ozempic, Wegovy) and tirzepatide (Mounjaro, Zepbound) turned two drug makers, Novo Nordisk
and Eli Lilly, into some of the most valuable companies in the world, and moved the shares of firms
people expect to lose from them (device makers, snack and soft-drink companies). Three questions:

1. How much does GLP-1 news move these stocks, and which news matters?
2. How lasting was the re-rating of the businesses expected to lose, and what does Lilly's price assume?
3. Can a forecast of the share price stay honest when the news is this lumpy, and can it be updated as
   news arrives?

## What was built

- **A catalyst ledger** (`data/ledger/catalysts.csv`, CC BY 4.0): 116 dated, sourced announcements from
  2017 to 2026, each with a type fixed in advance and a timestamp whose precision is stated
  ([ledger.md](ledger.md)).
- **Free public data only**: Yahoo Finance prices, Ken French factors, SEC filings, Wikipedia page views and
  Kalshi prices, so anyone can rerun the study ([data.md](data.md)).
- **A protocol written before the results**, with numbered amendments for every change made afterwards
  ([methodology.md](methodology.md)). Each step was read by an independent reviewer who did not write it;
  their findings changed the code and the wording more than once (see the amendments).
- **A forecast engine and a live page** that redraws the forecast when the visitor chooses how the
  next announcements turn out, plus a public, hash-chained ledger of every nightly forecast.

## What the news did

**Signed average moves are indistinguishable from zero (F1).** Good and bad news cancel inside each
event type and company, and none of the cells with enough events is rejected at a 10% false-discovery
rate. That says the test has little power for signed averages, not that news does not matter.

**The size of the move is large (F2).** On earnings days the stocks move about twice what the
factor models expect: Lilly earnings 1.75 (p = 0.009) and Novo earnings 1.64 (p = 0.008) in standardised
units, where 0.8 is what no news would give. For Novo's earnings this partly reflects other news on the
same days: Novo earnings fall to 1.06 (p = 0.146) when confounded days are dropped. Trial readouts and Lilly's own earnings hold up.

**Guidance surprises matter, weight-loss surprises are not established (F3, F4).** Lilly's three-day move
followed the size of its guidance revision at 2.9 pp per 1% of the guidance midpoint (permutation p = 0.013,
9 clean events). For
trial readouts, how far the weight loss beat the previous record did not explain the move in the clean
sample, and was borderline (p = 0.05) with all nine trials, so the intuitive story is not demonstrated.

**The losers were re-rated, and it stuck (F5).** Using synthetic difference-in-differences against 373 S&P
500 stocks, the 11 perceived losers fell -10.5% (1.8) in the month after the SELECT cardiovascular
result of 2023-08-08 and -19.3% (3.6) after a year, with no recovery. The caveats matter as much as the
number: other news landed in the same weeks, the loser list was fixed with hindsight, and the donor pool
is today's index. After the first 22%-weight-loss readout in 2022 there is no comparable effect (F6).

**GLP-1 exposure is not a stable trait of a stock (F7), and spillovers are real but modest (F8).**
A stock's exposure to a makers-minus-losers factor in one period tells almost nothing about the next
(rank correlation 0.078 (p = 0.100)), so the live page does not offer a "GLP-1 beta screen". Spillovers
between baskets were highest since 2025 (total connectedness 16.5%, against 12.1% before SELECT), with
drug makers transmitting to the losers; this is a descriptive pattern, not proof of causation.

**What Lilly's price assumes (F9, F10).** Working backwards from Lilly's market value after valuing the
rest of the business at peer multiples, the price is consistent with about $479bn (280-894) of yearly
peak tirzepatide sales, against $49.5bn over the last twelve months. That is an upper bound, because it
credits the whole premium to one franchise. Lilly's days with catalogued GLP-1 news were 7% of trading
days and produced 22.0% of its log return since mid-2022.

**Public attention adds a sliver, if anything (F11).** Wikipedia page views for the drugs improve a plain
volatility model by about 1% for Lilly (p = 0.002) but not when measured as a change, and the effect
comes from newer pages that trend upward, so it may be a regime proxy. The forecast does not use it.

## The forecast, and how it did

The forecast engine compares four ways to forecast the log return of Lilly and Novo at 1 to 252
trading days: a random walk, a GARCH model (the industry workhorse), the same with resampled shocks,
and an **event-driven jump model** (GARCH volatility with news days clipped, plus earnings jumps and
unscheduled jumps sized from the ledger) with **adaptive conformal calibration** of its interval width.
All were scored by CRPS, which rewards sharp and honest distributions, over a development period and
a test period fixed beforehand.

**The jump model did not forecast better (F12).** Across 24 comparisons one passes the decision rule
(Novo at one day, a 0.6% gain), and with that many tests a pass or two is expected by chance. On two stocks
with big, famous news days, a plain GARCH or random walk is about as good in CRPS as a model that knows the
calendar. The likely reason, not tested, is that GARCH already learns the event risk from past news days.

**Where the engine helps is calibration.** The GARCH intervals were too narrow when regimes changed
(Novo's 80% interval covered 49-51% of outcomes at 63 days in the test period); the conformal step brought
average coverage error down to 0.025 in development and 0.078 in test, against 0.057 and 0.110 for the
random walk. That is a few independent windows in one regime, so it supports "the intervals are widened
to match recent misses", not "the intervals are right".

**Updating with the news (F13).** The live page changes the forecast when the visitor sets how an upcoming
earnings report or the FDA decision on CagriSema turns out (default: the model's historical mix and
the Kalshi market's price). Every weekday evening the engine adds a new forecast to a public,
hash-chained ledger and scores forecasts as their horizons pass. At the time of writing the ledger is
days old, so F13 is a mechanism, not a result.

## What this does not show

- Two stocks, one regime of extraordinary growth, and a ledger of 116 events curated by one person with
  hindsight: the statistics are indicative, and every claim is stated with its sample size.
- The study did not build a patient-funnel valuation or value Novo (amendment 9), did not use news text or
  language models (amendment 10), did not run a foundation-model baseline or an option-implied benchmark
  (amendment 11), and cannot archive option chains with free keyless data (amendment 12).
- Nothing here predicts direction. The live page shows a range, and a visitor who sets an outcome gets the
  model's range conditional on that assumption, not a forecast of it.

## Reproduce

`uv sync && uv run glp1 doctor && uv run glp1 ingest && uv run glp1 build && uv run glp1 study`, then
`ecosystem`, `valuation`, `attention`, `forecast`; `uv run pytest` ties every number in these documents to
the results files. The live page and the nightly ledger are described in [nightly.md](nightly.md).
