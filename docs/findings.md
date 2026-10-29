# Findings register

Not investment advice. One row per claim in [the study](study.md): how strong it is, what backs it, and
which test keeps the document and the results in step. `tests/test_governance.py` fails if a row loses its
evidence file or its checking test, or if the study mentions a finding that is not here.

Strength scale: **robust** (survives the checks that were run and a plausible alternative), **suggestive**
(statistically supported but narrow, hindsight-dependent or one regime), **exploratory** (seen once or after
looking at the data), **not established** (tested and not supported), **mechanism** (a process that exists, with
no result yet).

| ID | Claim | Strength | Evidence | Checked by |
|---|---|---|---|---|
| F1 | Signed average event moves are not distinguishable from zero; no cell is rejected at a 10% false-discovery rate | robust (as a statement about power) | results/eventstudy.json, docs/event-study.md | tests/test_results_docs.py |
| F2 | News days move the stocks about twice the modelled size on earnings and trial readouts; Novo earnings lose this when confounded days are dropped | robust for Lilly earnings and readouts, suggestive for Novo earnings | results/eventstudy.json, docs/event-study.md | tests/test_results_docs.py |
| F3 | The size of a guidance revision predicts the three-day move | suggestive (small n, carries the earnings surprise) | results/eventstudy.json | tests/test_results_docs.py |
| F4 | A weight-loss result beating the record predicts the move | not established | results/eventstudy.json | tests/test_results_docs.py |
| F5 | The 11 perceived losers were re-rated downward after SELECT (2023-08-08) and it persisted | suggestive (other news in the window, hindsight choice of shock and losers) | results/ecosystem.json, docs/ecosystem.md | tests/test_ecosystem_docs.py |
| F6 | No comparable re-rating after SURMOUNT-1 (2022-04-28) | not established (effect absent, medtech subset only at 4 weeks) | results/ecosystem.json | tests/test_ecosystem_docs.py |
| F7 | A stock's GLP-1 factor beta is not stable across periods | robust (rank correlation 0.078) | results/factor.json | tests/test_ecosystem_docs.py |
| F8 | Spillover between baskets was highest since 2025, drug makers transmitting to losers | exploratory (no null benchmark) | results/connectedness.json | tests/test_ecosystem_docs.py |
| F9 | Lilly's price implies about $479bn of yearly peak tirzepatide sales (an upper bound) | suggestive (assumption band, premium credited to one franchise) | results/valuation.json, docs/valuation.md | tests/test_valuation_docs.py |
| F10 | 7% of trading days with catalogued news produced 22.0% of Lilly's log return since mid-2022 | robust (raw returns, includes market moves) | results/valuation.json | tests/test_valuation_docs.py |
| F11 | Page views add about 1% to a volatility model's fit for Lilly, none as a change | exploratory (likely regime proxy) | results/attention.json, docs/attention.md | tests/test_attention_docs.py |
| F12 | The jump model does not beat GARCH or a random walk in CRPS; conformal calibration improves interval coverage | robust for "no practical CRPS gain", suggestive for calibration (few independent windows) | results/forecast_scores.json, docs/forecast.md | tests/test_forecast_docs.py |
| F13 | Every weekday forecast is committed to a public hash-chained ledger and scored when its horizon passes | mechanism (no scored history yet) | forecasts/ledger.jsonl, docs/nightly.md | tests/test_nightly.py |

## What changed because of review

Independent reviewers read steps 3, 4, 6 and 7 and found faults that changed published numbers or wording.
They are recorded in the amendments in [methodology.md](methodology.md); the main ones were a missing-day
bug that dropped whole events, a donor pool that still held 33 industry peers, an attention index that spiked
at each page's launch (which turned a "no effect" into a small effect), and a bootstrap baseline with
a built-in drift plus development origins whose outcomes fell in the test period.
