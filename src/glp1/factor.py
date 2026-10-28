"""A tradable-in-principle GLP-1 factor and a GLP-1 beta for every S&P 500 stock.

Factor: equal-weight makers (LLY, NVO) minus equal-weight perceived losers, made orthogonal to the
Fama-French factors, so a stock's beta to it is not market beta in disguise. Betas come from a
regression of each stock's excess return on the six factors plus this factor, over two
non-overlapping windows. Stability is the rank correlation of the two sets of betas and how the
first window's top and bottom quintiles behave in the second (methodology section 4).
"""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import polars as pl
from scipy import stats

from glp1.config import FREEZE_DATE, Paths
from glp1.ecosystem import GROUPS, NOT_DONORS

MAKERS = ["LLY", "NVO"]
LOSERS = GROUPS["all_losers"]
FF = ["mkt_rf", "smb", "hml", "rmw", "cma", "mom"]
WINDOW_A = (date(2023, 1, 1), date(2024, 12, 31))
WINDOW_B = (date(2025, 1, 1), FREEZE_DATE)
FACTOR_END = date(2026, 9, 30)  # the Fama-French file ends here (amendment 1)


def returns(paths: Paths, con) -> pl.DataFrame:
    """Long daily simple returns for the donors and the universe, with the factors joined."""
    donors = pl.read_parquet(paths.processed / "donors.parquet")
    uni = pl.from_arrow(con.sql("select ticker, date, adj_close from eligible_prices").arrow())
    px = (
        pl.concat([donors, uni.select(donors.columns)])
        .unique(["ticker", "date"])
        .sort("ticker", "date")
    )
    ret = px.with_columns(ret=pl.col("adj_close").pct_change().over("ticker")).drop_nulls("ret")
    fac = pl.from_arrow(con.sql("select * from factors").arrow())
    return ret.join(fac, on="date", how="inner").with_columns(ex=pl.col("ret") - pl.col("rf"))


def build_factor(ret: pl.DataFrame) -> pl.DataFrame:
    """Daily raw factor and its FF6-orthogonal version (date, raw, glp1)."""
    wide = ret.pivot(on="ticker", index="date", values="ret").sort("date")
    losers = [c for c in LOSERS if c in wide.columns]
    raw = wide.select(
        "date",
        raw=pl.mean_horizontal(*MAKERS) - pl.mean_horizontal(*losers),
    ).drop_nulls()
    fac = ret.select("date", *FF).unique("date")
    d = raw.join(fac, on="date")
    x = np.column_stack([np.ones(d.height)] + [d[c].to_numpy() for c in FF])
    beta, *_ = np.linalg.lstsq(x, d["raw"].to_numpy(), rcond=None)
    return d.select("date", "raw").with_columns(glp1=d["raw"].to_numpy() - x @ beta)


def window_betas(
    ret: pl.DataFrame, fac: pl.DataFrame, window, min_obs: int = 200
) -> dict[str, float]:
    """GLP-1 beta of every ticker over one window (regression on the FF6 factors and the factor)."""
    d = ret.join(fac.select("date", "glp1"), on="date").filter(
        pl.col("date").is_between(*window) & (pl.col("date") <= FACTOR_END)
    )
    out = {}
    for (tk,), g in d.group_by("ticker"):
        if g.height < min_obs:
            continue
        x = np.column_stack([np.ones(g.height)] + [g[c].to_numpy() for c in [*FF, "glp1"]])
        b, *_ = np.linalg.lstsq(x, g["ex"].to_numpy(), rcond=None)
        out[tk] = float(b[-1])
    return out


def pca_check(ret: pl.DataFrame) -> float:
    """|correlation| of the factor's FF6-orthogonal series with the first principal component of the
    13 names' FF6 residuals: does one common GLP-1 axis exist without our weights?"""
    names = [t for t in MAKERS + LOSERS]
    wide = (
        ret.pivot(on="ticker", index="date", values="ex")
        .select("date", *[n for n in names if n in ret["ticker"].unique()])
        .drop_nulls()
    )
    fac = ret.select("date", *FF).unique("date")
    d = wide.join(fac, on="date").sort("date")
    x = np.column_stack([np.ones(d.height)] + [d[c].to_numpy() for c in FF])
    cols = [c for c in wide.columns if c != "date"]
    res = np.column_stack(
        [d[c].to_numpy() - x @ np.linalg.lstsq(x, d[c].to_numpy(), rcond=None)[0] for c in cols]
    )
    res = (res - res.mean(0)) / res.std(0)
    u, s, _ = np.linalg.svd(res, full_matrices=False)
    pc1 = u[:, 0] * s[0]
    f = build_factor(ret).join(d.select("date"), on="date", how="inner").sort("date")
    return float(abs(np.corrcoef(pc1, f["glp1"].to_numpy())[0, 1]))


def pca_detail(ret: pl.DataFrame) -> dict:
    """Which principal component of the 13 names' FF6 residuals matches the factor, and how related
    the makers' and losers' residuals are (the direct evidence for or against a common axis)."""
    names = [t for t in MAKERS + LOSERS if t in set(ret["ticker"].unique())]
    wide = ret.pivot(on="ticker", index="date", values="ex").select("date", *names).drop_nulls()
    d = wide.join(ret.select("date", *FF).unique("date"), on="date").sort("date")
    x = np.column_stack([np.ones(d.height)] + [d[c].to_numpy() for c in FF])
    res = np.column_stack(
        [d[c].to_numpy() - x @ np.linalg.lstsq(x, d[c].to_numpy(), rcond=None)[0] for c in names]
    )
    mk = res[:, [names.index(m) for m in MAKERS]].mean(axis=1)
    lo = res[:, [names.index(n) for n in LOSERS if n in names]].mean(axis=1)
    z = (res - res.mean(0)) / res.std(0)
    u, s, _ = np.linalg.svd(z, full_matrices=False)
    f = build_factor(ret).join(d.select("date"), on="date", how="inner").sort("date")["glp1"]
    corr = [abs(float(np.corrcoef(u[:, i] * s[i], f.to_numpy())[0, 1])) for i in range(4)]
    return {
        "maker_loser_resid_corr": float(np.corrcoef(mk, lo)[0, 1]),
        "pc_abs_corr_first4": corr,
        "best_pc": int(np.argmax(corr)) + 1,
    }


def run(paths: Paths) -> dict:
    from glp1 import warehouse

    con = warehouse.connect(paths)
    ret = returns(paths, con)
    fac = build_factor(ret)
    a = window_betas(ret, fac, WINDOW_A)
    b = window_betas(ret, fac, WINDOW_B)
    common = sorted(set(a) & set(b) - set(MAKERS) - set(LOSERS))
    # stability is studied on S&P 500 names outside the factor's own legs and the GLP-1 names
    sp500 = set(pl.read_parquet(paths.processed / "donors.parquet")["ticker"].unique())
    pool = [t for t in common if t in sp500 and t not in NOT_DONORS]
    xa = np.array([a[t] for t in pool])
    xb = np.array([b[t] for t in pool])
    rho = stats.spearmanr(xa, xb)
    q = max(len(pool) // 5, 1)
    order = np.argsort(xa)
    top, bottom = order[-q:], order[:q]
    ranked = sorted(pool, key=lambda t: b[t])
    res = {
        "factor_days": fac.height,
        "factor_mean_daily": float(fac["raw"].mean()),
        "factor_sd_daily": float(fac["raw"].std()),
        "pca_abs_corr": pca_check(ret),
        "pca": pca_detail(ret),
        "n_betas": len(pool),
        "spearman_ab": float(rho.statistic),
        "spearman_p": float(rho.pvalue),
        "top_quintile_b_minus_bottom_quintile_b": float(xb[top].mean() - xb[bottom].mean()),
        "most_positive_window_b": [(t, b[t]) for t in ranked[-10:][::-1]],
        "most_negative_window_b": [(t, b[t]) for t in ranked[:10]],
        "named": {
            t: {"a": a.get(t), "b": b.get(t)}
            for t in MAKERS + LOSERS + ["AMGN", "PFE", "TMO", "WST", "HIMS"]
        },
    }
    d = paths.root / "results"
    d.mkdir(exist_ok=True)
    (d / "factor.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    from glp1.config import get_paths

    r = run(get_paths())
    print({k: v for k, v in r.items() if k not in ("named",)})
