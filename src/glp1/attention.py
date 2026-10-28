"""Public attention to GLP-1 drugs (Wikipedia page views) and whether it helps predict volatility.

Page views are a free, daily, revision-proof attention measure. The test is deliberately plain: a
HAR volatility model (Corsi 2009: yesterday, last week and last month of absolute returns) against
the same model plus lagged attention, scored out of sample with a Diebold-Mariano test.
"""

from __future__ import annotations

import json
from datetime import date

import httpx
import numpy as np
import polars as pl
from scipy import stats

from glp1.config import FREEZE_DATE, Paths

ARTICLES = [
    "Ozempic",
    "Wegovy",
    "Mounjaro",
    "Zepbound",
    "Semaglutide",
    "Tirzepatide",
    "Eli_Lilly_and_Company",
    "Novo_Nordisk",
]
URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/"
    "all-access/user/{a}/daily/{start}/{end}"
)
UA = "glp1-market-lab/0.1 (https://github.com/deadmigue55/glp1-market-lab)"


def fetch(paths: Paths, start: str = "20170101") -> pl.DataFrame:
    """Daily English-Wikipedia user page views of each article, cut at the freeze date."""
    rows = []
    end = FREEZE_DATE.strftime("%Y%m%d")
    with httpx.Client(headers={"User-Agent": UA}, timeout=60) as client:
        for a in ARTICLES:
            f = paths.raw / "wikipedia" / f"{a}.json"
            if f.exists():
                items = json.loads(f.read_text(encoding="utf-8"))["items"]
            else:
                r = client.get(URL.format(a=a, start=start, end=end))
                if r.status_code == 404:  # no data before the page existed
                    continue
                r.raise_for_status()
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(r.content)
                items = r.json()["items"]
            rows += [(a, i["timestamp"][:8], i["views"]) for i in items]
    df = pl.DataFrame(rows, schema=["article", "day", "views"], orient="row").with_columns(
        date=pl.col("day").str.to_date("%Y%m%d")
    )
    out = df.select("article", "date", "views").sort("article", "date")
    out.write_parquet(paths.processed / "pageviews.parquet")
    return out


def attention_index(pv: pl.DataFrame) -> pl.DataFrame:
    """Daily GLP-1 attention: mean of each drug page's log views standardised on its own history
    up to that day (expanding), so the index never uses later data."""
    drugs = ["Ozempic", "Wegovy", "Mounjaro", "Zepbound", "Semaglutide", "Tirzepatide"]
    wide = (
        pv.filter(pl.col("article").is_in(drugs))
        .pivot(on="article", index="date", values="views")
        .sort("date")
    )
    cols = [c for c in wide.columns if c != "date"]
    z = []
    for c in cols:
        x = np.log1p(wide[c].fill_null(0).to_numpy().astype(float))
        mu = np.cumsum(x) / np.arange(1, len(x) + 1)
        var = np.cumsum(x**2) / np.arange(1, len(x) + 1) - mu**2
        z.append(
            np.where(np.arange(len(x)) > 60, (x - mu) / np.sqrt(np.maximum(var, 1e-9)), np.nan)
        )
    return wide.select("date").with_columns(attention=np.nanmean(np.column_stack(z), axis=1))


def har_frame(ret: pl.DataFrame, att: pl.DataFrame) -> pl.DataFrame:
    """Target and regressors for one security, indexed by trading day t (information up to t)."""
    d = ret.sort("date").with_columns(a=pl.col("r").abs())
    d = d.with_columns(
        d1=pl.col("a"), d5=pl.col("a").rolling_mean(5), d22=pl.col("a").rolling_mean(22)
    )
    # target: log of the mean absolute return over days t+1..t+5
    fut = sum(pl.col("a").shift(-k) for k in range(1, 6)) / 5
    d = d.with_columns(y=(fut + 1e-4).log())
    d = d.with_columns(*[(pl.col(c) + 1e-4).log().alias(c) for c in ("d1", "d5", "d22")])
    d = d.join(att, on="date", how="left").with_columns(
        att5=pl.col("attention").rolling_mean(5),
        att_chg=pl.col("attention") - pl.col("attention").shift(5),
    )
    cols = ["y", "d1", "d5", "d22", "att5", "att_chg"]
    return d.drop_nulls(cols).filter(pl.all_horizontal(pl.col(c).is_finite() for c in cols))


def expanding_forecasts(d: pl.DataFrame, base: list[str], extra: list[str], first: date, step=5):
    """One-step (5-day-ahead) expanding-window OLS forecasts; refit every ``step`` days."""
    days = d["date"].to_list()
    y = d["y"].to_numpy()
    xb = np.column_stack([np.ones(d.height)] + [d[c].to_numpy() for c in base])
    xe = np.column_stack([xb] + [d[c].to_numpy() for c in extra])
    start = next(i for i, x in enumerate(days) if x >= first)
    fb, fe, act = [], [], []
    beta_b = beta_e = None
    for i in range(start, len(days)):
        if (i - start) % step == 0:
            tr = slice(0, i - 5)  # the target of day i-5 ends at day i: no overlap with the future
            beta_b = np.linalg.lstsq(xb[tr], y[tr], rcond=None)[0]
            beta_e = np.linalg.lstsq(xe[tr], y[tr], rcond=None)[0]
        fb.append(xb[i] @ beta_b)
        fe.append(xe[i] @ beta_e)
        act.append(y[i])
    return np.array(fb), np.array(fe), np.array(act)


def dm_test(e1: np.ndarray, e2: np.ndarray, h: int = 5) -> tuple[float, float]:
    """Diebold-Mariano test on squared-error loss with a Newey-West variance (h-1 lags)."""
    d = e1**2 - e2**2
    n = len(d)
    dm = d - d.mean()
    lrv = dm @ dm / n
    for k in range(1, h):
        lrv += 2 * (1 - k / h) * (dm[k:] @ dm[:-k]) / n
    stat = d.mean() / np.sqrt(lrv / n)
    return float(stat), float(2 * stats.norm.sf(abs(stat)))


def run(paths: Paths, con) -> dict:
    pv = fetch(paths)
    att = attention_index(pv)
    px = pl.from_arrow(
        con.sql(
            "select ticker, date, adj_close from eligible_prices where ticker in ('LLY','NVO')"
        ).arrow()
    )
    out = {}
    for tk in ("LLY", "NVO"):
        r = (
            px.filter(pl.col("ticker") == tk)
            .sort("date")
            .with_columns(r=pl.col("adj_close").log().diff())
            .drop_nulls("r")
        )
        d = har_frame(r.select("date", "r"), att)
        res = {}
        for name, extra in (
            ("level", ["att5"]),
            ("change", ["att_chg"]),
            ("both", ["att5", "att_chg"]),
        ):
            fb, fe, act = expanding_forecasts(d, ["d1", "d5", "d22"], extra, date(2023, 1, 1))
            stat, p = dm_test(act - fb, act - fe)
            res[name] = {
                "n": len(act),
                "mse_har": float(np.mean((act - fb) ** 2)),
                "mse_har_attention": float(np.mean((act - fe) ** 2)),
                "gain_pct": float(100 * (1 - np.mean((act - fe) ** 2) / np.mean((act - fb) ** 2))),
                "dm_stat": stat,
                "dm_p": p,
            }
        out[tk] = res
    result = {
        "articles": ARTICLES,
        "pageview_rows": pv.height,
        "first_page_date": {
            a: str(pv.filter(pl.col("article") == a)["date"].min()) for a in ARTICLES
        },
        "volatility_test": out,
    }
    d_ = paths.root / "results"
    d_.mkdir(exist_ok=True)
    (d_ / "attention.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result
