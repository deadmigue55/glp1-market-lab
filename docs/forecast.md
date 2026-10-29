# Forecast engine: does an event-driven jump model beat GARCH?

Not investment advice. These are predictive distributions for the size and spread of a stock's
move, scored against what happened. They carry no direction signal and no recommendation.
Numbers come from `results/forecast_scores.json` and are checked by `tests/test_forecast_docs.py`.
Protocol: `methodology.md` section 6 and amendment 11. Code: `forecast.py`.

## Models and test

Targets are the log return of LLY and NVO at 1, 5, 21, 63, 126 and 252 trading days, forecast every
week (304 origins from 2021-01-04). Development origins run to 2025-10-31 (252), test origins from
2025-11-03; only origins whose horizon has completed are scored. A development origin whose outcome
falls after 2025-10-31 is dropped (embargoed), so no development score uses test-period prices.

- **B0** random walk, zero drift, trailing 252-day volatility, normal.
- **B1** GJR-GARCH(1,1) with Student-t errors, zero mean.
- **B2** the same GARCH with resampled standardised residuals (filtered historical simulation); the
  residual pool is re-centred to zero mean. (The first run did not do this and B2 carried a drift of
  about 28% a year for Lilly; an independent review found it and the backtest was rerun.)
- **M1** jump-diffusion: GARCH fitted with news-day returns clipped to 2.5 trailing standard deviations,
  plus scheduled earnings jumps (size from past ledger events; the quarterly calendar is projected
  from the last quarterly report every 91 days, so the date can be off by a week or two; off-cycle
  guidance changes count as unscheduled jumps) and unscheduled compound-Poisson jumps (rate and size from past ledger events). Only
  events whose window had closed before the origin are used.
- **M2** M1 with adaptive conformal calibration of the interval width (Gibbs and Candes 2021), updated
  only with outcomes already known at each origin.

Scores: CRPS from 99 quantiles (lower is better); coverage of the 50/80/90% intervals; a one-sided
Diebold-Mariano test with Harvey's correction and a bandwidth that covers the overlap of horizons.
A method counts as beating the best baseline only if it is better on development CRPS, p < 0.10, and
better again in the test period. The baseline is the one with the lowest development CRPS for that
security and horizon.

## Result 1: no practical gain in CRPS

Primary comparison (horizons 21 and 63), mean CRPS:

| Security | h | Best baseline | Dev: baseline | Dev: M1 | Dev: M2 | M1 DM p | Test: baseline | Test: M1 | Test: M2 |
|---|---|---|---|---|---|---|---|---|---|
| LLY | 21 | B0 | 0.0520 | 0.0519 | 0.0523 | 0.36 | 0.0467 | 0.0454 | 0.0465 |
| LLY | 63 | B1 | 0.0868 | 0.0871 | 0.0891 | 0.71 | 0.0857 | 0.0863 | 0.0863 |
| NVO | 21 | B0 | 0.0539 | 0.0535 | 0.0542 | 0.11 | 0.0901 | 0.0911 | 0.0906 |
| NVO | 63 | B0 | 0.0996 | 0.1001 | 0.1018 | 0.71 | 0.1297 | 0.1336 | 0.1327 |

Across all 24 security-horizon-model comparisons one passes the decision rule: M1 for Novo at one day
(development CRPS 0.01122 for B1 against 0.01115, p = 0.04; test 0.01680 against 0.01673). That is a
0.6% improvement, and with 24 tests at the 10% level two or three passes are expected by chance, so it
is not evidence of a gain. Elsewhere the jump layer is level with the baseline in development (a few
cells at p near 0.1, none clearing the rule together with the test period) and the sign flips in the
test period. The development-period CRPS averaged over all cells up to 126 days is 0.0679 for B0, 0.0681
for B1, 0.0683 for B2, 0.0677 for M1 and 0.0692 for M2: the models are separated by far less than their
sampling error. The honest summary is that on two stocks with big, famous news days, a plain GARCH or
even a trailing-volatility random walk is about as good as the event-aware model in CRPS. A possible
reason is that the GARCH already absorbs most event risk through the volatility it learns from past
news days, so a quarterly jump added on top counts that risk twice; this was not tested. Cells with
fewer than about 30 weekly origins have no usable Diebold-Mariano test (the bandwidth for long horizons
swallows the sample) and show no p-value; this covers the test period at 126 days and every catalyst
subset in the test period.

## Result 2: calibration is where the engine helps, within limits

Intervals from the GARCH baselines are too narrow when the regime changes. In the test period, Novo's
80% interval at 21 days covered 58% of outcomes for B1 and 58% for B2 (77% for the random walk), against
88% for M2; at 63 days B1 and B2 covered 49% and 51% against 90% for M2. Averaged over horizons up to
126 days and both stocks, the distance of 80% coverage from nominal is:

| Model | Development | Test |
|---|---|---|
| B0 | 0.057 | 0.110 |
| B1 | 0.093 | 0.132 |
| B2 | 0.089 | 0.130 |
| M1 | 0.066 | 0.100 |
| M2 | 0.025 | 0.078 |

M2 pays for this with a slightly worse CRPS (0.0692 against 0.0679 for B0 in development), so the
trade is wider but better-calibrated intervals, not sharper ones. M2's test error is partly
over-coverage: at 126 days its 80% interval covered 96% of Lilly outcomes and 100% of Novo's, and so did
every other model for Novo. **How much weight this carries.** Weekly origins with 63-day targets
overlap heavily: Novo's 39 test origins at 63 days are about three independent windows in one regime
(the stock's 2025 collapse), so the 49%, 51% and 90% figures are one episode, not a calibration
estimate. The development period, with 240 origins over several regimes, tells the same story at a
smaller size. The live page shows M2's intervals and describes them as widened to match recent misses,
not as accurate.

## Limits

- Two stocks, 252 development and 48-52 test origins at the short horizons, 26 at 126 days and none at
  252: the long-horizon rows are development only. The test period is one regime.
- Twenty-four comparisons were tested with no multiplicity correction; read single p-values as
  descriptive.
- No Chronos-Bolt or other foundation-model baseline was run, and no option-implied benchmark exists
  yet (amendment 11); the study cannot claim to beat either.
- One M1 configuration was tried. A better jump model may exist; this one did not beat the baselines.
- Test and development periods were scored in the same run. No model was changed afterwards.
