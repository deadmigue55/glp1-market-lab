# Ecosystem: re-rating, shock transmission and a GLP-1 factor

Not investment advice. Descriptive statistics about the past. Numbers come from `results/ecosystem.json`,
`results/factor.json` and `results/connectedness.json` and are checked by `tests/test_ecosystem_docs.py`.
Protocol: `methodology.md` section 4 and amendments 8-9. Rerun with `uv run glp1 ecosystem` (about 30 min).
An independent review of this step led to a wider donor screen, more placebo draws, in-time placebos and
the softer wording below.

## H4: were the perceived losers re-rated, and did it last?

Method: synthetic difference-in-differences (Arkhangelsky et al. 2021) on weekly log prices from June
2018, 11 perceived losers against 373 S&P 500 donors. Donors exclude the pharma, device, health-service,
food and agriculture industries by SEC SIC code, plus named peers the codes miss (drug wholesalers, CROs,
life-science tools, grocery-heavy retailers, household staples, cruise lines, health REITs); the rules
were fixed before the weights were computed, and the list of named peers was extended after the review
found 33 such names in the first pool (the SELECT estimates moved by about one point). The Python port
reproduces the R `synthdid` estimate to 1e-6 on a fixture panel (`tests/test_sdid.py`). The plain
baseline is the basket's change in mean log price minus SPY's.

Two shocks were fixed from ledger events before the run: SELECT (2023-08-08, the first outcomes trial
to show a cardiovascular benefit) and SURMOUNT-1 (2022-04-28, the first 22%-weight-loss readout).
Effects are log points, about percent for these sizes. The standard error is the larger of the placebo
standard error (100 draws of random donor subsets) and the standard deviation of the effects at 12 fake
shock dates before 2022. The effect is the average gap over the post window, not the gap at its end.

| Treated group | Weeks after SELECT | SDID effect (s.e.) | Plain basket vs SPY | Gap in the last week |
|---|---|---|---|---|
| All 11 losers | 4 | -10.5% (1.8) | -5.5% | -13.6% |
| All 11 losers | 13 | -17.9% (2.2) | -12.7% | -23.4% |
| All 11 losers | 26 | -18.4% (2.5) | -13.5% | -15.8% |
| All 11 losers | 52 | -19.3% (3.6) | -16.8% | -26.3% |
| Medtech and health | 13 | -22.4% (3.8) | -15.8% | -28.3% |
| Food and drink | 13 | -9.8% (3.0) | -7.3% | -15.0% |
| Food and drink | 52 | -17.0% (7.0) | -18.3% | -24.1% |

**Reading.** The losers fell about 10% relative to their synthetic counterparts in the month after
SELECT and 18-19% on average over six and twelve months, and the gap did not close: this is consistent
with H4's persistence claim (beyond 60 days) for SELECT. Medtech and health services drove the early
fall; food converged later and its estimates are weak (the one-year food estimate is 2.4 standard errors
from zero, the 13-week one 3.3, but both come from four stocks). The plain basket-minus-SPY understates
the effect by 3-5 points, because SPY is not a good counterfactual for these names. After SURMOUNT-1
only the medtech subset at four weeks reaches two standard errors (-5.9%, s.e. 2.9) and it is gone by
13 weeks; for example all losers at 13 weeks: -3.0% (s.e. 3.1). The gap path is not smooth: at 26 weeks the last-week gap (-15.8%) is shallower
than the window average, and the fitted time weight sits almost entirely on the last pre-shock week
(0.91-1.00), so the estimate is close to "change since the week before SELECT, relative to donors"
(with uniform time weights the 52-week answer is -25.7%).

**Limits, in order of importance.**
- **Not SELECT alone.** The post window holds other news. The ledger has Lilly's Q2 report on the same
  morning, Novo's outlook raise on 2023-10-13 and both Q3 reports on 2023-11-02, and the gap deepens in
  those autumn weeks. SDID removes what the donors share, not what is specific to these 11 stocks, so this
  is "the period that started with SELECT".
- **Chosen with hindsight.** The loser list was fixed after the stocks' falls were known, and SELECT was
  picked as the shock after the event study (amendment 8). Two shocks and four horizons are reported with
  no correction for multiplicity.
- **Survivorship.** Donors are today's index members, so firms that left are missing and those that rose
  are over-represented. A review sensitivity that dropped 36 recent additions and large winners moved
  the 4/13/26/52-week estimates by at most one point; the bias leans toward more negative effects.
- **Small treated group.** Eleven treated units and one dominant shock: the standard errors are
  indicative, not exact.

## A GLP-1 factor, and how far a stock's exposure can be trusted

Factor: equal-weight makers (LLY, NVO) minus equal-weight losers, orthogonalised to the six
Fama-French factors; 2448 days, daily mean 0.04%, sd 1.68%. Betas are estimated for 450 S&P 500 stocks over
2023-24 and again over 2025 to the freeze.

- The rank correlation between the two windows' betas is 0.078 (p = 0.100): a stock's GLP-1 beta in one
  window says almost nothing about the next, and the spread in window-two betas between the window-one
  top and bottom quintiles is 0.010. The factor describes the makers-versus-losers spread, not a
  stable property of other stocks.
- The makers' and losers' Fama-French residuals correlate 0.08 with each other, so there is little
  common GLP-1 axis in daily returns. The factor matches the third principal component of the 13 names'
  residuals (correlation 0.91, against 0.22 and 0.31 for the first two): it exists, but as a weak
  contrast, and it is built from the same names, so the match is partly by construction.
- The highest window-two betas among the remaining S&P 500 names are pharma and biotech (BIIB, ABBV,
  MRNA, MRK, REGN), so the factor is largely a pharma-sector tilt. The live page therefore shows betas
  as exploratory and not as a screening tool.

## Connectedness of the baskets

TVP-VAR (Antonakakis et al. 2020; the Python port matches R `ConnectednessApproach` to 1e-14 on a
fixture panel of total connectedness), daily market-neutral returns of five baskets (makers,
challengers, supply chain, medtech losers, food losers), generalised FEVD at ten days.

| Period | Total connectedness | Net transmitters | Net receivers |
|---|---|---|---|
| to 2023-08 | 12.1% | makers (+1.0) | supply (-0.7) |
| 2023-08 to 2024-12 | 7.1% | challengers (+1.1) | food losers (-1.1) |
| 2025 on | 16.5% | makers (+1.5), challengers (+1.3) | medtech losers (-1.5), food losers (-1.0) |

Connectedness was lowest during the re-rating of 2023-24 and highest since 2025, and in that last period
the net flow runs from the drug makers and challengers toward the losers. These are descriptive
period averages with no null benchmark: the index swings by several points inside a period, the net
values are about one to one and a half percentage points, and net directional values were not checked
against R. Read them as a pattern to watch, not as proof of transmission.
