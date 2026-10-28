# Attention: does public interest in GLP-1 drugs predict volatility?

Not investment advice. Numbers come from `results/attention.json` and are checked by
`tests/test_attention_docs.py`. Protocol: `methodology.md` section 8 and amendment 10. Code:
`attention.py`.

## What was done

Daily English-Wikipedia page views of six pages (Ozempic, Wegovy, Mounjaro, Zepbound, Semaglutide,
Tirzepatide; first available 2017-2023 depending on the page) form a daily attention index: each page's
log views standardised on its own history up to that day, then averaged. Two further pages (Eli Lilly,
Novo Nordisk) are stored but not in the index.

The test asks whether attention helps forecast the next five trading days' volatility of Lilly and Novo
beyond what recent volatility already says. Baseline: a HAR model (Corsi 2009) of the log mean absolute
return over days t+1 to t+5 on yesterday's, last week's and last month's absolute returns. Challenger:
the same plus lagged attention (its five-day mean, its five-day change, or both). Expanding-window
out-of-sample forecasts from 2023-01-01 (953 days), refitted every five days, no overlap between a
fitting target and the forecast period; scored by squared error with a Diebold-Mariano test.

## Result: no gain

| Security | Attention term | MSE change | DM statistic | p-value |
|---|---|---|---|---|
| LLY | level | -0.2% | -0.27 | 0.783 |
| LLY | change | +0.0% | 0.38 | 0.705 |
| LLY | both | -0.2% | -0.26 | 0.792 |
| NVO | level | +0.6% | 0.59 | 0.553 |
| NVO | change | +0.0% | 0.16 | 0.870 |
| NVO | both | +0.5% | 0.57 | 0.571 |

(MSE change is the reduction relative to HAR, so positive is better.) No variant improves on the HAR
baseline by more than about half a percent and none is close to significant. In this data, how loudly the
public talks about GLP-1 drugs adds nothing to what yesterday's price moves already say about next
week's volatility. The forecast engine therefore does not use attention as an input; it is reported
because a null result on a plausible idea is part of the study.

## Limits

- Page views measure retail curiosity, not the professional news flow that moves these stocks; daily
  news counts (GDELT) were not available (rate limits) and would be a better test of the news channel.
- Absolute returns are a noisy volatility proxy; intraday data would sharpen it but is not free.
- One window, one lag structure, two stocks. A null here is not proof of no relationship.
- No language-model or text-sentiment feature is used anywhere in this release (see amendment 10).
