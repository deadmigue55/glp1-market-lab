# Event study: what moved the stocks, and by how much

Not investment advice. Descriptive statistics about the past; nothing here says what a stock will do.
Every number below is in `results/eventstudy.json` and is checked against it by
`tests/test_results_docs.py`. Protocol: `methodology.md` section 3 and amendments 1-7. Rerun with
`uv run glp1 study` (about 40 s). An independent review of this step led to amendment 7; the claims
below are the ones that survived it.

## Sample

116 ledger events give 332 primary (event, security) pairs; 7 use the market-model fallback because the
Fama-French file ends 2026-09-30 and has no factor data for their `[-1,+1]` window (amendment 1). A
missing day voids only the windows that contain it. The four 2017 events have no 250-day estimation
window and are skipped. Primary quantity: CAR over day -1 to day +1, Fama-French five factors plus
momentum. "Clean" drops the 44 events flagged confounded; "all" keeps them. Both are shown because the
clean sample loses most of the large moves.

## What the data say

**1. Signed average moves are indistinguishable from zero.** Of 13 event type x company cells with at
least five clean events, none is rejected at a 10% false-discovery rate (Benjamini-Hochberg), and none
of the 17 cells with at least five events (clean or not) has a Kolari-Pynnonen or wild-bootstrap p-value
below 5% for the three-day window. Good and bad news cancel inside a cell, so a signed average has
little power here: this is a statement about the test, not proof that news does not move prices.

**2. The size of the move is large, and this is the robust finding.** Mean absolute standardised CAR is
about 0.8 if the news moved nothing (a reviewer's placebo run on random non-event days of Lilly and Novo gave
0.70-0.77, not saved in the results file, so the threshold is if anything a little generous). With all events: Lilly earnings 1.75 (p = 0.009), Novo
earnings 1.64 (p = 0.008), Novo trial readouts 2.04 (p = 0.021). Benjamini-Hochberg at 10% across the
30 size tests keeps three: Lilly earnings, Novo earnings and Lilly's move on Novo's earnings (1.35,
p = 0.010). Clean events only: Lilly earnings 1.55 (p = 0.050), Novo trial readouts 1.85 (p = 0.040),
but **Novo earnings fall to 1.06 (p = 0.146)**, so "twice the modelled size" holds for readouts and
for Lilly, and for Novo earnings only because of days when other news arrived.

**3. H1: the surprise matters for guidance revisions.** Slope of CAR[-1,+1] on the surprise, HC3 errors,
with a permutation p-value because n is small:

| Surprise | Sample | n | Slope | t | Permutation p |
|---|---|---|---|---|---|
| Lilly guidance revision (% of midpoint) | clean | 9 | 2.9 pp per 1% | 2.9 | 0.013 |
| Lilly guidance revision (% of midpoint) | all | 22 | 1.8 pp per 1% | 3.8 | 0.005 |
| Novo guidance revision (pp of growth) | clean | 8 | 0.7 pp per pp | 4.4 | 0.038 |
| Novo guidance revision (pp of growth) | all | 16 | 1.6 pp per pp | 1.3 | 0.028 |
| Weight loss vs record (pp) | clean | 6 | 0.9 pp per pp | 0.5 | 0.314 |
| Weight loss vs record (pp) | all | 9 | 1.0 pp per pp | 2.5 | 0.051 |

The guidance result is real in the sense that it survives a permutation test, but a guidance revision
arrives with the quarter's earnings, so the slope also carries the earnings surprise itself. The
weight-loss version, which was the pre-stated trial-readout hypothesis, is **not** established: nothing
in the clean sample and a borderline p = 0.05 with all nine trials.

**4. H2 (read-through): untested, not refuted.** A pooled signed mean cannot test "a negative result for
one leader raises the other". No read-through cell has a three-day KP p-value below 0.13. What is
significant is the size of the rival's move on earnings day (finding 2). Conditioning on the sign of the
sponsor's own move needs more events than the ledger holds.

**5. H3 (pricing and policy): not testable.** The ledger holds four such events and only one cell has
three usable windows (HIMS). Declared untestable under amendment 6(d).

**6. H5 (drift after the news): weak, unreplicated.** CAR[+2,+20] after Novo trial readouts is negative
in every Novo cell: -3.8% on NVO (all events, KP p = 0.027, bootstrap p = 0.081), -5.1% on NVO with clean
events (KP p = 0.012, bootstrap p = 0.011) and -6.7% on NOVO-B.CO (clean, n = 6, KP p = 0.037,
bootstrap p = 0.101). These are overlapping samples of the same events, not three findings. Of the 12
clean-sample drift cells with at least five observations, two have KP p < 0.05 and one has bootstrap
p < 0.05; the smallest p-value is 0.011, against a Benjamini-Hochberg threshold of 0.10 / 12 = 0.0083,
so none survives multiplicity. Reported as a candidate for the out-of-sample period, not as a finding.

**7. H4 (re-rating of losers)** needs the synthetic difference-in-differences of step 4.

## Jump-size model

CAR_i ~ Normal(a_g, sd_i^2 + tau_g^2), partial pooling over event type x company (PyMC, NUTS, 4 chains;
no C++ compiler, so it runs in Python mode in about 10 s per fit). One observation per issuer and day 0
(a Lilly earnings release and readout on the same day count once, as a readout). Only Lilly and Novo
are modelled: the four other-sponsor readouts (three Viking moves of +123%, -28% and +40%, one Amgen)
are too few and too extreme to pool, and they loosened the shared prior for everyone else.
`tau` is the spread of news moves beyond estimation noise, posterior mean and 90% interval:

| Group | n all | tau, all events | n clean | tau, clean only | tau, all, Student-t |
|---|---|---|---|---|---|
| Lilly earnings/guidance | 24 | 6.7% (4.9-8.5) | 11 | 5.5% (3.4-8.0) | 4.4% (2.5-6.4) |
| Novo earnings/guidance | 27 | 7.4% (5.8-9.3) | 13 | 3.8% (1.5-6.2) | 4.4% (2.3-6.5) |
| Lilly trial readouts | 6 | 8.0% (5.7-11.3) | 4 | 5.4% (2.7-9.0) | 4.8% (2.2-8.3) |
| Novo trial readouts | 18 | 8.1% (6.3-10.6) | 13 | 6.9% (4.6-9.9) | 5.1% (2.7-7.9) |

Read this as a range, not a point: restricting to unconfounded days roughly halves Novo's earnings
spread, and a heavy-tailed likelihood shrinks every group because it explains the largest moves as tail
events instead of spread. The forecast engine will take the "all events" column as the realistic
size of a catalyst day (confounding is how news arrives) and carry the other two as sensitivity
scenarios. Group means `a_g` are all within one posterior sd of zero.

## Caveats

- Kolari-Pynnonen aligns residuals in event time over all pairs, so for events on different dates the
  average cross-correlation is about zero (90% of cells have |rbar| below 0.025; the largest, 0.35, is a
  three-event HIMS cell) and KP is
  close to BMP on this ledger. It protects against same-day clustering only where it exists.
- The estimation window is not purged of other ledger events, which inflates residual sigma somewhat for
  Lilly, so standardised CARs are slightly understated.
- A Lilly earnings release and a trial readout on the same day appear in both event-type cells, and the
  jump model counts that day once.
- 44 of 116 events are confounded. Amendment 6 was written after the first look at the signed means and
  the CAR ranking: items (a)-(c) are exploratory.
- Copenhagen close is fixed at 17:00 and half sessions are not modelled (`data.md`).
