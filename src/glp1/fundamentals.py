"""Point-in-time company fundamentals from SEC XBRL (companyfacts).

Every value carries the date its filing reached EDGAR (``filed``), so a daily series built with
``as_of`` never uses a number before the market could see it. Flows are turned into single quarters
(a fourth quarter is the fiscal year minus the nine-month year-to-date); balances are instants.
"""

from __future__ import annotations

import json
from datetime import date

import polars as pl

from glp1.config import Paths
from glp1.ingest.edgar import EdgarClient

CIKS = {
    "LLY": 59478,
    "MRK": 310158,
    "BMY": 14272,
    "ABBV": 1551152,
    "PFE": 78003,
    "AMGN": 318154,
    "JNJ": 200406,
    "GILD": 882095,
}
REVENUE = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
]
# tags are listed by priority; companies switch tags over time, so all of them are merged
CASH = ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsAndShortTermInvestments"]
SECURITIES = [
    "MarketableSecuritiesCurrent",
    "ShortTermInvestments",
    "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
]
DEBT_LT = ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"]
DEBT_ST = ["DebtCurrent", "LongTermDebtCurrent", "ShortTermBorrowings"]
SHARES = ["EntityCommonStockSharesOutstanding"]


def facts(paths: Paths, client: EdgarClient, ticker: str) -> dict:
    cik = CIKS[ticker]
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    body = client.cached(f"facts/CIK{cik:010d}.json", url, f"facts-{ticker}")
    return json.loads(body)["facts"]


def _rows(f: dict, tags: list[str], taxonomy: str = "us-gaap", unit: str = "USD") -> pl.DataFrame:
    """Observations from every tag in ``tags``; on a repeated period the first tag wins."""
    frames = []
    for prio, tag in enumerate(tags):
        obs = f.get(taxonomy, {}).get(tag, {}).get("units", {}).get(unit)
        if not obs:
            continue
        df = pl.DataFrame(obs).with_columns(
            pl.col("end").str.to_date(),
            pl.col("filed").str.to_date(),
            (pl.col("start").str.to_date() if "start" in obs[0] else pl.lit(None, pl.Date)).alias(
                "start"
            ),
            prio=pl.lit(prio),
        )
        frames.append(df.select("start", "end", "filed", "val", "form", "prio"))
    empty = pl.DataFrame(
        schema={
            "start": pl.Date,
            "end": pl.Date,
            "filed": pl.Date,
            "val": pl.Float64,
            "form": pl.String,
            "prio": pl.Int64,
        }
    )
    if not frames:
        return empty
    df = pl.concat(frames).filter(pl.col("form").is_in(["10-Q", "10-K", "10-K/A", "10-Q/A"]))
    return df.with_columns(pl.col("val").cast(pl.Float64))


def quarterly_flow(f: dict, tags: list[str]) -> pl.DataFrame:
    """Single-quarter (end, val, filed) from three-month, nine-month and annual facts."""
    d = _rows(f, tags).filter(pl.col("start").is_not_null())
    d = d.with_columns(days=(pl.col("end") - pl.col("start")).dt.total_days())
    # keep the first filing that reported each (start, end) period
    d = d.sort("prio", "filed").unique(["start", "end"], keep="first", maintain_order=True)
    q = d.filter(pl.col("days").is_between(80, 100)).select("end", "val", "filed")
    ann = d.filter(pl.col("days").is_between(350, 380))
    out = [q]
    for a in ann.iter_rows(named=True):
        nine = d.filter(
            (pl.col("start") == a["start"])
            & pl.col("days").is_between(260, 285)
            & (pl.col("end") < a["end"])
        )
        if nine.height and not q.filter(pl.col("end") == a["end"]).height:
            out.append(
                pl.DataFrame(
                    {
                        "end": [a["end"]],
                        "val": [a["val"] - nine["val"][0]],
                        "filed": [max(a["filed"], nine["filed"][0])],
                    }
                )
            )
    return pl.concat(out).sort("end")


def instant(f: dict, tags: list[str], taxonomy: str = "us-gaap") -> pl.DataFrame:
    d = _rows(f, tags, taxonomy).sort("prio", "filed")
    d = d.unique(["end"], keep="first", maintain_order=True)
    return d.select("end", "val", "filed").sort("end")


def ttm(q: pl.DataFrame) -> pl.DataFrame:
    """Trailing-four-quarter sum, dated by the filing that completed the window."""
    q = q.sort("end")
    return (
        q.with_columns(
            ttm=pl.col("val").rolling_sum(4),
            filed=pl.col("filed").rolling_max(4),
            span=(pl.col("end") - pl.col("end").shift(3)).dt.total_days(),
        )
        .filter(pl.col("ttm").is_not_null() & pl.col("span").is_between(250, 290))
        .select("end", "ttm", "filed")
    )


def as_of(series: pl.DataFrame, col: str, day: date) -> float | None:
    """Latest value filed on or before ``day``."""
    s = series.filter(pl.col("filed") <= day).sort("end")
    return float(s[col][-1]) if s.height else None


def build(paths: Paths) -> pl.DataFrame:
    """One row per (ticker, quarter): revenue, cash, debt and the filing date of the revenue."""
    client = EdgarClient(paths)
    try:
        rows = []
        for tk in CIKS:
            f = facts(paths, client, tk)
            rev = quarterly_flow(f, REVENUE).rename({"val": "revenue", "filed": "filed_rev"})
            parts = {
                "cash": instant(f, CASH),
                "securities": instant(f, SECURITIES),
                "debt_lt": instant(f, DEBT_LT),
                "debt_st": instant(f, DEBT_ST),
            }
            df = rev
            for name, part in parts.items():
                df = df.join(part.rename({"val": name}).drop("filed"), on="end", how="left")
            rows.append(df.with_columns(ticker=pl.lit(tk)))
    finally:
        client.close()
    out = pl.concat(rows).with_columns(
        net_debt=pl.col("debt_lt").fill_null(0)
        + pl.col("debt_st").fill_null(0)
        - pl.col("cash").fill_null(0)
        - pl.col("securities").fill_null(0)
    )
    out.write_parquet(paths.processed / "fundamentals_q.parquet")
    return out


def shares_series(paths: Paths, ticker: str) -> pl.DataFrame:
    """Shares outstanding on each filing's cover date, dated by the filing (point-in-time)."""
    client = EdgarClient(paths)
    try:
        f = facts(paths, client, ticker)
    finally:
        client.close()
    d = _rows(f, SHARES, "dei", "shares")
    return (
        d.sort("filed").unique(["filed"], keep="first").select("filed", shares="val").sort("filed")
    )
