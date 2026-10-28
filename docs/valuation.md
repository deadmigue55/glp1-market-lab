# Valuation: what the Lilly share price assumes about GLP-1 sales

Not investment advice. This converts a past price into the sales it would take to justify it under
stated assumptions. It is not a sales forecast and says nothing about whether the stock is cheap or
dear. Numbers come from `results/valuation.json`; `tests/test_valuation_docs.py` checks them.
Protocol: `methodology.md` section 5 and amendment 9. Code: `fundamentals.py`, `rdcf.py`,
`valuation.py`.

## Method in four steps

1. **Enterprise value, point in time.** Unadjusted close times the latest filed share count, plus the
   latest filed net debt (long and short debt less cash and short-term investments). Every input is
   used only from the date its SEC filing was public (`tests/test_fundamentals.py`).
2. **Value of the rest of the business.** Trailing four-quarter revenue excluding tirzepatide
   (Mounjaro and Zepbound; Trulicity stays in the base) times the median EV / sales of five large-cap
   peers (Merck, Bristol-Myers Squibb, AbbVie, Pfizer, Johnson & Johnson), which is 5.96 today. The
   quartiles of the peers (25th and 75th percentile) give a low and a high base multiple.
3. **Residual.** EV minus step 2 is what the market pays for the franchise.
4. **Implied peak sales.** Discount a sales path (a six-year ramp from current sales to a peak, a
   plateau until exclusivity ends, then a 20% annual decline) at a free-cash-flow margin, and solve for
   the peak. The solution is a band over a grid: discount rate 6%, 7.5%, 9%; after-tax cash margin 25%,
   34%, 42%; exclusivity ending 7, 10 or 14 years out (27 combinations).

Product sales come from Lilly's earnings releases (`data/fundamentals/glp1_product_revenue.csv`, with
a source URL per row; quarterly totals equal the SEC XBRL revenue for all 17 quarters).

## Result: the residual moved with the stock

| Date | Enterprise value | Tirzepatide trailing sales | Residual | Implied peak sales, median (low-high) |
|---|---|---|---|---|
| 2019-12-31 | $141bn | $0.0bn | $35bn | $16bn (10-30) |
| 2022-04-28 | $296bn | $0.0bn | $150bn | $70bn (41-128) |
| 2023-08-08 | $511bn | $2.0bn | $377bn | $175bn (103-321) |
| 2024-12-31 | $760bn | $13.4bn | $647bn | $295bn (173-546) |
| 2025-12-31 | $1049bn | $30.3bn | $920bn | $415bn (243-771) |
| 2026-10-27 | $1253bn | $49.5bn | $1073bn | $479bn (280-894) |

**Reading.** Between the Mounjaro launch quarter and today the price has multiplied Lilly's enterprise
value more than fourfold, and the sales it implies for the franchise at the same assumptions rose from
about $70bn to about $480bn, against $49.5bn of trailing tirzepatide sales. The base multiple barely
matters (using the 25th or 75th percentile peer moves the 2026 median between $468bn and $513bn): the
uncertainty is in the discount rate, margin and exclusivity assumptions, which is why the answer is a
band and not a number.

**What this is not.** The residual is Lilly's whole premium over a pharma peer multiple, not tirzepatide
alone. Before any tirzepatide sales (2019) it was already $35bn, which the method would read as $16bn of
peak sales. The premium also pays for orforglipron, retatrutide, the faster growth of Lilly's other
products and its margins. So the implied figures are an upper bound for what the market assumes about
the current franchise, and they are useful for comparing dates and the same assumptions, not as a level.
Change since 2019 in the residual ($1038bn) is a cleaner indicator of what arrived with GLP-1.

## News days

Lilly's log return from mid-May 2022 to the freeze is 1.518 (a factor of 4.6). On the 78 trading days
(of 1118) that fall in a ledger window for a Lilly or Novo event, the sum of daily log returns is 0.334,
which is 22.0% of the total. So 7% of the days produced about a fifth of the return, and the remaining
four-fifths accrued on days with no catalogued GLP-1 news. These sums include market moves on the same
days and are raw returns, not abnormal ones.

## Limits

- Five peers, one valuation date convention, and EV / sales instead of a cash-flow model for the rest of
  the business; peers have pipelines and shocks of their own.
- Tirzepatide sales enter on the day of the 10-Q or 10-K filing, a few days after the earnings release,
  which delays information slightly and is conservative.
- Unadjusted close is used because market value is a price actually paid; the factor models elsewhere in
  this project use dividend-adjusted prices.
- Novo Nordisk is not valued here. Its filings carry no US-GAAP tags and its share count is not in
  the XBRL feed, and the 2026 first-quarter sales include a one-off DKK 26.8bn provision reversal; the
  curated Novo product file is kept for the forecast engine.
