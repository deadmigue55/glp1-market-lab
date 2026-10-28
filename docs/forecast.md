# Forecast engine: does an event-driven jump model beat GARCH?

Not investment advice. These are predictive distributions for the size and spread of a stock's
move, scored against what happened. They carry no direction signal and no recommendation.
Numbers come from `results/forecast_scores.json` and are checked by `tests/test_forecast_docs.py`.
Protocol: `methodology.md` section 6 and amendment 11. Code: `forecast.py`.

## Models and test

Targets are the log return of LLY and NVO at 1, 5, 21, 63, 126 and 252 trading days, forecast every
week (304 origins from 2021-01-04). Development origins run to 2025-10-31 (252), test origins from
2025-11-03; only origins whose horizon has completed are scored.

- **B0** random walk, zero drift, trailing 252-day volatility, normal.
- **B1** GJR-GARCH(1,1) with Student-t errors, zero mean.
- **B2** the same GARCH with resampled standardised residuals (filtered historical simulation).
- **M1** jump-diffusion: GARCH fitted with news-day returns clipped to 2.5 trailing standard deviations,
  plus scheduled earnings jumps (size from past ledger events, quarterly calendar projected from the
  last report) and unscheduled compound-Poisson jumps (rate and size from past ledger events). Only
  events whose window had closed before the origin are used.
- **M2** M1 with adaptive conformal calibration of the interval width (Gibbs and Candes 2021), updated
  only with outcomes already known at each origin.

Scores: CRPS from 99 quantiles (lower is better); coverage of the 50/80/90% intervals; a one-sided
Diebold-Mariano test with Harvey's correction and a bandwidth that covers the overlap of horizons.
A method counts as beating the best baseline only if it is better on development CRPS, p < 0.10, and
better again in the test period. The baseline is the one with the lowest development CRPS for that
security and horizon.

## Result 1: no demonstrated gain in CRPS

Primary comparison (horizons 21 and 63), mean CRPS:

| Security | h | Best baseline | Dev: baseline | Dev: M1 | Dev: M2 | M1 DM p | Test: baseline | Test: M1 | Test: M2 |
|---|---|---|---|---|---|---|---|---|---|
| LLY | 21 | B2 | 0.0516 | 0.0534 | 0.0537 | 0.87 | 0.0449 | 0.0454 | 0.0466 |
| LLY | 63 | B2 | 0.0824 | 0.0944 | 0.0967 | 0.94 | 0.0889 | 0.0866 | 0.0867 |
| NVO | 21 | B0 | 0.0547 | 0.0543 | 0.0549 | 0.15 | 0.0901 | 0.0911 | 0.0898 |
| NVO | 63 | B0 | 0.0989 | 0.0991 | 0.1018 | 0.60 | 0.1297 | 0.1334 | 0.1332 |

Across all 24 security-horizon-model comparisons none passes the decision rule. The jump layer does
not help in development and the sign is not stable in the test period. Within 21 days before a
scheduled report the result is the same (no model beats the baseline there either). The honest
summary is: on two stocks with big, famous news days, a plain GARCH or even a trailing-volatility
random walk is as good as the event-aware model in CRPS. The likely reason is that the GARCH already
absorbs most of the event risk through the volatility it learns from past news days, and a quarterly
jump added on top counts that risk twice; this explanation was not tested.

## Result 2: calibration is where the engine helps

Intervals from the GARCH baselines are too narrow when the regime changes. In the test period, Novo's
80% interval at 21 days covered 58% of outcomes for B1 and 56% for B2 (77% for the random walk), against
85% for M2; at 63 days B1 and B2 covered 49% and 51% against 95% for M2. Averaged over horizons up to
126 days and both stocks, the distance of 80% coverage from nominal is:

| Model | Development | Test |
|---|---|---|
| B0 | 0.056 | 0.110 |
| B1 | 0.101 | 0.132 |
| B2 | 0.067 | 0.128 |
| M1 | 0.079 | 0.105 |
| M2 | 0.020 | 0.080 |

M2 pays for this with a slightly worse CRPS (0.0707 against 0.0693 for B0 in development), so the
trade is wider but honest intervals, not sharper ones. The live page therefore shows M2's intervals
and says in plain words that they are calibrated, not that they are accurate.

## Limits

- Two stocks, 252 development and 48-52 test origins at the short horizons, 26 at 126 days and none at
  252: the long-horizon rows are development only. The test period is one regime.
- No Chronos-Bolt or other foundation-model baseline was run, and no option-implied benchmark exists
  yet (amendment 11); the study cannot claim to beat either.
- One M1 configuration was tried. A better jump model may exist; this one did not beat the baselines.
- Test and development periods were scored in the same run. No model was changed afterwards.
