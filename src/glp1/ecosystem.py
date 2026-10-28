"""Ecosystem analysis: did GLP-1 news permanently re-rate the perceived losers? (hypothesis H4).

Synthetic difference-in-differences on weekly log prices. Treated units are the perceived losers of
the universe; donors are S&P 500 names outside the GLP-1-exposed industries (``ingest.sic``). Shock
dates are ledger events fixed in ``SHOCKS`` before the method was run (methodology section 4).
The baseline is the plain event-study answer: the treated basket's return in excess of SPY.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import numpy as np
import polars as pl

from glp1 import sdid
from glp1.config import Paths
from glp1.ingest import sic

PANEL_START = date(2018, 6, 1)  # INSP lists in May 2018
PLACEBO_REPS = 50
HORIZONS = (4, 13, 26, 52)  # post-shock weeks
SHOCKS = {  # ledger event_id -> day 0
    "NVO-20230808-select": date(2023, 8, 8),
    "LLY-20220428-surmount1": date(2022, 4, 28),
}
GROUPS = {
    "all_losers": [
        "DXCM",
        "PODD",
        "RMD",
        "INSP",
        "DVA",
        "ISRG",
        "ZBH",
        "MDLZ",
        "HSY",
        "PEP",
        "CAG",
    ],
    "medtech_health": ["DXCM", "PODD", "RMD", "INSP", "DVA", "ISRG", "ZBH"],
    "food_drink": ["MDLZ", "HSY", "PEP", "CAG"],
}
NOT_DONORS = {"LLY", "NVO", "AMGN", "PFE", "VKTX", "HIMS", "TMO", "WST", "WW", "SPY"}


def weekly_log_prices(paths: Paths, con) -> pl.DataFrame:
    """Wide table: one row per Friday-ending week, one column per ticker (week's last close)."""
    donors = pl.read_parquet(paths.processed / "donors.parquet")
    uni = pl.from_arrow(con.sql("select ticker, date, adj_close from eligible_prices").arrow())
    px = pl.concat([donors, uni.select(donors.columns)]).unique(["ticker", "date"])
    px = px.filter(pl.col("date") >= PANEL_START).with_columns(
        week=pl.col("date").dt.truncate("1w") + pl.duration(days=4)  # the Friday of that week
    )
    last = px.sort("date").group_by("ticker", "week").agg(pl.col("adj_close").last())
    return (
        last.with_columns(y=pl.col("adj_close").log())
        .pivot(on="ticker", index="week", values="y")
        .sort("week")
    )


def donor_pool(paths: Paths, wide: pl.DataFrame, treated: list[str]) -> list[str]:
    """Donors: outside the excluded SIC ranges, not a GLP-1 name, complete over the whole panel."""
    codes = pl.read_parquet(paths.processed / "donor_sic.parquet")
    ok = {r["ticker"] for r in codes.iter_rows(named=True) if not sic.excluded(r["sic"])}
    complete = {c for c in wide.columns if c != "week" and wide[c].null_count() == 0}
    return sorted((ok & complete) - NOT_DONORS - set(treated))


def run_shock(wide: pl.DataFrame, donors: list[str], treated: list[str], day0: date, h: int):
    """SDID estimate (log points) and the plain basket-minus-SPY answer, one shock and horizon."""
    shock_week = day0 - timedelta(days=day0.weekday()) + timedelta(days=4)
    pre = wide.filter(pl.col("week") < shock_week)
    post = wide.filter(pl.col("week") >= shock_week).head(h)
    if post.height < h:
        return None
    both = pl.concat([pre, post])
    cols = donors + treated
    y = both.select(cols).to_numpy().T
    n0, t0 = len(donors), pre.height
    fit = sdid.estimate(y, n0, t0)
    se = sdid.placebo_se(y, n0, t0, reps=PLACEBO_REPS)
    # baseline: treated average minus SPY, change from the pre-period mean to the post-period mean
    tr = y[n0:].mean(axis=0)
    spy = both["SPY"].to_numpy()
    base = (tr[t0:].mean() - tr[:t0].mean()) - (spy[t0:].mean() - spy[:t0].mean())
    return {
        "att": fit.att,
        "se": se,
        "baseline_did_vs_spy": float(base),
        "n_donors": n0,
        "t_pre": t0,
        "t_post": h,
        "effective_donors": float(1 / np.sum(fit.omega**2)),
    }


def run(paths: Paths) -> dict:
    from glp1 import warehouse

    con = warehouse.connect(paths)
    wide = weekly_log_prices(paths, con)
    out = []
    for event_id, day0 in SHOCKS.items():
        for gname, treated in GROUPS.items():
            tr = [t for t in treated if t in wide.columns and wide[t].null_count() == 0]
            donors = donor_pool(paths, wide, treated)
            for h in HORIZONS:
                r = run_shock(wide, donors, tr, day0, h)
                if r:
                    out.append(
                        {
                            "event_id": event_id,
                            "group": gname,
                            "horizon_weeks": h,
                            "n_treated": len(tr),
                        }
                        | r
                    )
    res = {"panel_weeks": wide.height, "estimates": out}
    d = paths.root / "results"
    d.mkdir(exist_ok=True)
    (d / "ecosystem.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    from glp1.config import get_paths

    r = run(get_paths())
    for e in r["estimates"]:
        print(
            e["event_id"][-9:],
            e["group"],
            e["horizon_weeks"],
            f"{100 * e['att']:.1f}% se {100 * e['se']:.1f} "
            f"base {100 * e['baseline_did_vs_spy']:.1f} donors {e['n_donors']}",
        )
