# Ecosystem: re-rating, shock transmission and a GLP-1 factor

Not investment advice. Descriptive statistics about the past. Numbers come from `results/ecosystem.json`,
`results/factor.json` and `results/connectedness.json` and are checked by `tests/test_ecosystem_docs.py`.
Protocol: `methodology.md` section 4 and amendment 8. Rerun with `uv run glp1 ecosystem` (about 15 min).

## H4: did the losers get re-rated, and did it last?

Method: synthetic difference-in-differences (Arkhangelsky et al. 2021) on weekly log prices from June
2018, 11 perceived losers against 403 S&P 500 donors outside the pharma, device, health-service and
food industries (SEC SIC codes, fixed before the weights were computed). Placebo standard errors from
50 draws. The Python port reproduces the R `synthdid` estimate to 1e-6 on a fixture panel
(`tests/test_sdid.py`). The baseline is the plain basket-minus-SPY change in mean log price.

Shocks were fixed before the run: SELECT (2023-08-08, the first outcomes trial to show a cardiovascular
benefit) and SURMOUNT-1 (2022-04-28, the first 22%-weight-loss readout). Effects are log points, about
percent for these sizes.

| Treated group | Weeks after SELECT | SDID effect (placebo s.e.) | Plain basket vs SPY |
|---|---|---|---|
| All 11 losers | 4 | -9.6% (1.0) | -5.5% |
| All 11 losers | 13 | -16.5% (1.7) | -12.7% |
| All 11 losers | 26 | -17.4% (2.4) | -13.5% |
| All 11 losers | 52 | -18.9% (3.4) | -16.8% |
| Medtech and health | 13 | -21.2% (2.0) | -15.8% |
| Food and drink | 13 | -8.5% (3.0) | -7.3% |
| Food and drink | 52 | -16.4% (5.7) | -18.3% |

**Reading.** After SELECT the losers fell about 10% in a month and 17-19% by six to twelve months
relative to their synthetic counterparts, and the fall did not reverse: H4 holds for the persistence
test (beyond 60 days). Medtech and health services drove the early fall; food converged later. The
plain basket-minus-SPY understates the effect by 3-5 points, because SPY is not a good counterfactual
for these names. After SURMOUNT-1 no group shows an effect distinguishable from zero at any horizon
(for example all losers at 13 weeks: -1.9%, s.e. 3.3).

**Limits, in order of importance.**
- The post window around SELECT holds other news (Lilly's Q2 results the same morning, the autumn 2023
  earnings seasons, rate moves that hit growth names). SDID removes what the donors share, not what is
  specific to these 11 stocks, so this is "the period that started with SELECT", not SELECT alone.
- The donors are today's index members, so firms that left the index are missing (survivorship).
- 11 treated units, placebo standard errors from 50 draws and a single dominant shock: the s.e. are
  indicative, not exact.
- SURMOUNT-1 comes with mostly the Lilly-Novo duopoly story already priced; absence of an effect is not
  proof that none exists.

## A GLP-1 factor, and how far a stock's exposure can be trusted

Factor: equal-weight makers (LLY, NVO) minus equal-weight losers, orthogonalised to the six
Fama-French factors; 2448 days, daily mean 0.04%, sd 1.68%. Betas are estimated for 481 S&P 500 stocks over
2023-24 and again over 2025 to the freeze.

- The rank correlation between the two windows' betas is 0.083 (p = 0.070): a stock's GLP-1 beta in one
  window says almost nothing about the next. The spread in window-two betas between window-one top and
  bottom quintiles is 0.012. The factor describes the makers-versus-losers spread, not a stable property
  of other stocks.
- The first principal component of the 13 names' Fama-French residuals correlates 0.22 (absolute) with
  the factor, so there is no single strong common GLP-1 axis in daily returns.
- The highest window-two betas among S&P 500 names are pharma, biotech and CRO companies (CRL, IQV,
  BIIB, ABBV), which says the factor is largely a pharma-sector tilt. This is why the live page shows
  betas as exploratory and not as a screening tool.

## Connectedness of the baskets

TVP-VAR (Antonakakis et al. 2020; the Python port matches R `ConnectednessApproach` to 1e-14 on a
fixture panel), daily market-neutral returns of five baskets (makers, challengers, supply chain,
medtech losers, food losers), generalised FEVD at ten days.

| Period | Total connectedness | Net transmitters | Net receivers |
|---|---|---|---|
| to 2023-08 | 12.1% | makers (+1.0) | supply (-0.7) |
| 2023-08 to 2024-12 | 7.1% | challengers (+1.1) | food losers (-1.1) |
| 2025 on | 16.5% | makers (+1.5), challengers (+1.3) | medtech losers (-1.5), food losers (-1.0) |

Spillovers were weakest during the re-rating of 2023-24 and strongest since 2025, when shocks flow from
the drug makers to the losers. There is no sampling uncertainty on these numbers; they are descriptive
period averages, and the period boundaries were fixed in advance.
