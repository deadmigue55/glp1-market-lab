# Attention: does public interest in GLP-1 drugs predict volatility?

Not investment advice. Numbers come from `results/attention.json` and are checked by
`tests/test_attention_docs.py`. Protocol: `methodology.md` section 8 and amendment 10. Code:
`attention.py`.

## What was done

Daily English-Wikipedia page views of six pages (Ozempic, Wegovy, Mounjaro, Zepbound, Semaglutide,
Tirzepatide; first available 2017-2023 depending on the page) form a daily attention index: each page's
log views standardised on its own history from the page's first day up to that day, then averaged. Two further pages (Eli Lilly,
Novo Nordisk) are stored but not in the index.

The test asks whether attention helps forecast the next five trading days' volatility of Lilly and Novo
beyond what recent volatility already says. Baseline: a HAR model (Corsi 2009) of the log mean absolute
return over days t+1 to t+5 on yesterday's, last week's and last month's absolute returns. Challenger:
the same plus lagged attention (its five-day mean, its five-day change, or both). Expanding-window
out-of-sample forecasts from 2023-01-01 (953 days), refitted every five days, no overlap between a
fitting target and the forecast period; scored by squared error with a Diebold-Mariano test.

## Result: a small gain from the level, none from the change

| Security | Attention term | MSE change | DM statistic | p-value |
|---|---|---|---|---|
| LLY | level | +1.3% | 3.04 | 0.002 |
| LLY | change | +0.1% | 0.91 | 0.365 |
| LLY | both | +1.5% | 3.15 | 0.002 |
| NVO | level | +0.8% | 2.19 | 0.028 |
| NVO | change | +0.1% | 0.61 | 0.539 |
| NVO | both | +1.0% | 2.33 | 0.020 |

(MSE change is the reduction relative to HAR, so positive is better.) Adding the five-day mean of
attention (the level) cuts the squared error by about 1.3% for Lilly (DM p = 0.002) and 0.8% for Novo
(p = 0.028); adding its five-day change does nothing (p = 0.37 and 0.54). Six tests were run, and the
Lilly level result survives a Bonferroni correction (0.012), the Novo one does not.

**How much to believe it.** The gain is statistically detectable but economically tiny, and three things
argue for caution. It comes from the newer pages (Wegovy, Mounjaro, Zepbound, Tirzepatide): the
Ozempic and Semaglutide pages alone give nothing (p = 0.97 and 0.38, Lilly and Novo), and dropping
Zepbound only shrinks it. Newer pages trend upward over the test window, so a level can proxy for the
high-volatility regime of 2023-25 rather than carry news; the change variant, which removes the trend,
shows no effect. And the sample is one window of about four years. Read it as "attention may carry a
sliver of information about next week's volatility", not as a signal. The forecast engine does not use
it.

**Correction history.** The first run of this step reported no effect at all. An independent review
found that pages were standardised from before they existed (zero views), which made the index spike
at each launch. The index now starts each page at its first day of data; the numbers above are from the
corrected run.

## Limits

- Page views measure retail curiosity, not the professional news flow that moves these stocks; daily
  news counts (GDELT) were not available (rate limits) and would be a better test of the news channel.
- Absolute returns are a noisy volatility proxy; intraday data would sharpen it but is not free.
- One window, one lag structure, two stocks. A null here is not proof of no relationship.
- No language-model or text-sentiment feature is used anywhere in this release (see amendment 10).
