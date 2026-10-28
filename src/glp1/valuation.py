"""Daily market-implied GLP-1 sales for Lilly (and its attribution to news days).

Per day: enterprise value from the price and the latest filed shares and net debt; the rest of the
business valued at the quartiles of large-cap pharma EV / trailing sales; the residual converted to
implied peak GLP-1 sales by ``rdcf.band``. Every fundamental is used only from the day its filing
was public. Product sales for Lilly come from ``data/fundamentals/glp1_product_revenue.csv``.
"""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import polars as pl

from glp1 import fundamentals as fu
from glp1 import rdcf
from glp1.config import FREEZE_DATE, Paths
from glp1.ingest import yahoo

PEERS = ["MRK", "BMY", "ABBV", "PFE", "JNJ"]  # complete cash, debt and revenue tags
START = date(2019, 1, 2)


def close(paths: Paths, ticker: str) -> pl.DataFrame:
    """Unadjusted close (split-adjusted by Yahoo): market value needs the price actually paid."""
    got = yahoo.load_cached(paths, ticker)
    if got is None:
        raise FileNotFoundError(f"no cached prices for {ticker}; run `glp1 ingest` / `glp1 donors`")
    return got[0].filter(pl.col("date") <= FREEZE_DATE).select("date", "close")


def point_in_time(q: pl.DataFrame, shares: pl.DataFrame, days: list[date]) -> pl.DataFrame:
    """For each day, the TTM revenue, net debt and shares that were public on that day."""
    ttm = fu.ttm(q.select("end", val="revenue", filed="filed_rev")).sort("filed")
    bal = q.select("end", "net_debt", "filed_rev").sort("filed_rev")
    shares = shares.sort("filed")
    frame = pl.DataFrame({"date": days}).sort("date")
    out = (
        frame.join_asof(ttm.select("filed", "ttm"), left_on="date", right_on="filed")
        .join_asof(bal.select("filed_rev", "net_debt"), left_on="date", right_on="filed_rev")
        .join_asof(shares, left_on="date", right_on="filed")
    )
    return out.select("date", "ttm", "net_debt", "shares")


MILESTONES = ["2019-12-31", "2022-04-28", "2023-08-08", "2024-12-31", "2025-12-31"]


def peer_multiples(paths: Paths, q: pl.DataFrame) -> pl.DataFrame:
    """Daily EV / TTM sales of each peer, then the 25th, 50th and 75th percentile across peers."""
    rows = []
    for tk in PEERS:
        c = close(paths, tk).filter(pl.col("date") >= START)
        pit = point_in_time(
            q.filter(pl.col("ticker") == tk), fu.shares_series(paths, tk), c["date"].to_list()
        )
        d = c.join(pit, on="date").with_columns(
            evs=(pl.col("close") * pl.col("shares") + pl.col("net_debt")) / pl.col("ttm")
        )
        rows.append(d.select("date", tk=pl.col("evs")).rename({"tk": tk}))
    wide = rows[0]
    for r in rows[1:]:
        wide = wide.join(r, on="date", how="full", coalesce=True)
    arr = wide.sort("date").select(PEERS).to_numpy()
    return (
        wide.sort("date")
        .select("date")
        .with_columns(
            m25=np.nanpercentile(arr, 25, axis=1),
            m50=np.nanpercentile(arr, 50, axis=1),
            m75=np.nanpercentile(arr, 75, axis=1),
        )
    )


def lilly_glp1_ttm(prod: pl.DataFrame, q: pl.DataFrame) -> pl.DataFrame:
    """Tirzepatide (Mounjaro + Zepbound) trailing sales in USD, dated by the 10-Q/10-K filing."""
    tirz = prod.filter(
        pl.col("company").str.contains("(?i)lilly")
        & pl.col("product").is_in(["Mounjaro", "Zepbound"])
    )
    per = (
        tirz.group_by("period_end")
        .agg(val=pl.col("revenue").sum() * 1e6)
        .with_columns(end=pl.col("period_end").str.to_date())
    )
    filed = q.filter(pl.col("ticker") == "LLY").select("end", "filed_rev")
    allq = filed.join(per.select("end", "val"), on="end", how="left").with_columns(
        pl.col("val").fill_null(0.0)
    )
    return fu.ttm(allq.select("end", "val", filed="filed_rev")).rename({"ttm": "glp1_ttm"})


def run(paths: Paths) -> dict:

    q = pl.read_parquet(paths.processed / "fundamentals_q.parquet")
    prod = pl.read_csv(paths.root / "data" / "fundamentals" / "glp1_product_revenue.csv")
    mult = peer_multiples(paths, q)
    c = close(paths, "LLY").filter(pl.col("date") >= START)
    lq = q.filter(pl.col("ticker") == "LLY")
    pit = point_in_time(lq, fu.shares_series(paths, "LLY"), c["date"].to_list())
    g = lilly_glp1_ttm(prod, q).sort("filed")
    d = (
        c.join(pit, on="date")
        .join(mult, on="date", how="left")
        .sort("date")
        .join_asof(g.select("filed", "glp1_ttm"), left_on="date", right_on="filed")
        .with_columns(pl.col("glp1_ttm").fill_null(0.0))
        .drop_nulls(["ttm", "net_debt", "shares", "m50"])
    )
    series = []
    for r in d.iter_rows(named=True):
        ev = r["close"] * r["shares"] + r["net_debt"]
        base_rev = r["ttm"] - r["glp1_ttm"]
        cur = r["glp1_ttm"] / 1e9
        out = {
            "date": str(r["date"]),
            "ev_bn": ev / 1e9,
            "glp1_ttm_bn": cur,
            "base_multiple": r["m50"],
        }
        for tag, m in (("c", r["m50"]), ("lo", r["m75"]), ("hi", r["m25"])):
            resid = (ev - m * base_rev) / 1e9  # a higher base multiple leaves less for GLP-1
            out[f"value_{tag}_bn"] = resid
            out[f"peak_{tag}"] = rdcf.band(resid, cur) if resid > 0 else None
        series.append(out)
    snap = {s["date"]: s for s in series}
    miles = {}
    for m in MILESTONES:
        k = max((x for x in snap if x <= m), default=None)
        if k:
            miles[m] = snap[k]
    res = {
        "assumption_grid": rdcf.GRID,
        "ramp_years": 6.0,
        "decline": 0.20,
        "peers": PEERS,
        "glp1_definition": "tirzepatide (Mounjaro + Zepbound); Trulicity stays in the base",
        "latest": series[-1],
        "milestones": miles,
        "weekly": [s for i, s in enumerate(series) if i % 5 == 0],
        "news_day_attribution": attribution(paths),
    }
    out_dir = paths.root / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "valuation.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def attribution(paths: Paths) -> dict:
    """Share of Lilly's log return since mid-May 2022 earned on ledger news days."""
    from glp1 import ledger, warehouse

    con = warehouse.connect(paths)
    px = (
        pl.from_arrow(
            con.sql(
                "select date, adj_close from eligible_prices where ticker='LLY' order by date"
            ).arrow()
        )
        .with_columns(r=pl.col("adj_close").log().diff())
        .drop_nulls("r")
    )
    px = px.filter(pl.col("date") >= date(2022, 5, 13))  # first session after the Q1 2022 report
    led = ledger.load(paths)
    days = set()
    dates = px["date"].to_list()
    for ev in led.iter_rows(named=True):
        if "LLY" not in (ev["ticker"] or "") and "LLY" not in (ev["also_affects"] or ""):
            continue
        try:
            f, la = ledger.day0_window(
                ev["occurred_at"], ev["timing"], ev["stated_date"], "NYSE", dates
            )
        except (ValueError, IndexError):
            continue
        days.update(d for d in dates if f <= d <= la)
    r = px["r"].to_numpy()
    on = np.array([d in days for d in dates])
    return {
        "from": str(dates[0]),
        "to": str(dates[-1]),
        "total_log_return": float(r.sum()),
        "news_log_return": float(r[on].sum()),
        "news_days": int(on.sum()),
        "all_days": len(dates),
        "share_of_total": float(r[on].sum() / r.sum()),
    }
