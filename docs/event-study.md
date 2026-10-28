# Event study: what moved the stocks, and by how much

Not investment advice. Descriptive statistics about the past; nothing here says what a stock will do.
Every number below is in `results/eventstudy.json` and is checked against it by
`tests/test_results_docs.py`. Protocol: `methodology.md` section 3 and amendments 1-6. Rerun with
`uv run glp1 study` (about 15 s).

## Sample

116 ledger events give 262 primary (event, security) pairs; 4 use the market-model fallback because the
factor file ends 2026-09-30 (amendment 1). The four 2017 events have no 250-day estimation window and
are skipped. Primary quantity: CAR over day -1 to day +1, Fama-French five factors plus momentum.

## What the data say

**1. Signed average moves are indistinguishable from zero.** Of 12 event type x company cells with at
least five clean events, none is rejected at a 10% false-discovery rate (Benjamini-Hochberg), and none
of the 16 cells with at least five events (clean or not) has a Kolari-Pynnonen or wild-bootstrap p-value
below 5% for the three-day window. Good and bad news cancel inside a cell, so an average hides the
effect.

**2. The size of the move is large.** Mean absolute standardised CAR is 1.6-2.0 where 0.80 is expected
if the news moved nothing: Lilly earnings 1.75 (p = 0.009), Novo earnings 1.64 (p = 0.008), Novo trial
readouts 2.04 (p = 0.021). Typical GLP-1 news days are about twice the size the factor model implies.

**3. H1: the surprise matters.** Slope of CAR[-1,+1] on the surprise (HC3 errors):

| Surprise | Sample | n | Slope | t |
|---|---|---|---|---|
| Lilly guidance revision (% of midpoint) | clean | 9 | 2.9 pp per 1% | 2.9 |
| Lilly guidance revision (% of midpoint) | all | 22 | 1.8 pp per 1% | 3.8 |
| Novo guidance revision (pp of growth) | clean | 8 | 0.7 pp per pp | 4.4 |
| Novo guidance revision (pp of growth) | all | 16 | 1.6 pp per pp | 1.3 |
| Weight loss vs record (pp) | clean | 6 | 0.9 pp per pp | 0.5 |
| Weight loss vs record (pp) | all | 9 | 1.0 pp per pp | 2.5 |

Guidance revisions are the cleanest evidence; the weight-loss slope is about one percentage point of
price per point of weight loss but rests on nine trials. Small samples: read the sizes, not the stars.

**4. H2 (read-through): not supported.** No read-through cell (a rival's move on a leader's news) has a
KP p-value below 0.13 for the three-day window.

**5. H3 (pricing and policy): not testable.** The ledger holds four such events and only one cell has
three usable windows (HIMS). Declared untestable under amendment 6(d).

**6. H5 (drift): no evidence.** Of 16 cells, two have a KP p-value under 5% for CAR[+2,+20]: Novo trial
readouts, -3.8% on NVO and -6.7% on NOVO-B.CO. These are the same events on two listings, neither holds
under the bootstrap at 5%, and with 16 cells a chance rejection is expected. Reported, not claimed.

**7. H4 (re-rating of losers)** needs the synthetic difference-in-differences of step 4.

## Jump-size model

CAR_i ~ Normal(a_g, sd_i^2 + tau_g^2), partial pooling over event type x company (PyMC, NUTS, 4 chains,
0 divergences, max R-hat 1.002; no C++ compiler, so it runs in Python mode in about 10 s). `tau` is the
spread of news moves beyond estimation noise:

| Group | n | tau (posterior mean, 90% interval) |
|---|---|---|
| Lilly earnings/guidance | 26 | 6.9% (5.1-9.3) |
| Novo earnings/guidance | 27 | 7.7% (5.5-10.3) |
| Lilly trial readouts | 6 | 10.0% (5.7-16.6) |
| Novo trial readouts | 18 | 9.3% (6.6-12.6) |
| Other sponsors' trial readouts | 4 | 53.2% (31.7-87.9) |

A closed-form empirical-Bayes estimate gives the same ordering, somewhat larger (9-13% for the big two).
The group means `a_g` are all within one posterior sd of zero. These spreads are the jump sizes the
forecast engine will draw from.

## Caveats

- 44 of 116 events are flagged confounded; the clean sample drops most of the largest moves, so both
  samples are shown.
- The signed-mean tests have little power at n = 5-27 and a 3-day window.
- Amendment 6 was written after the first look at the signed means and the CAR ranking: items (a)-(c)
  are exploratory.
- Copenhagen close is fixed at 17:00 and half sessions are not modelled (`data.md`).
