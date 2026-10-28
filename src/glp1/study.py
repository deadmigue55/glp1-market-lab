"""Run the event study on the warehouse and the catalyst ledger (methodology section 3).

``run`` writes two files under ``results/``: ``event_cars.csv`` (one row per event, security and
model) and ``eventstudy.json`` (cell tests and the pre-stated hypotheses). Every number quoted in
the docs comes from them.
"""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import polars as pl

from glp1 import eventstudy as es
from glp1 import jumps, ledger, warehouse
from glp1.config import FREEZE_DATE, Paths

LISTINGS = {"NVO": ["NVO", "NOVO-B.CO"]}  # one issuer, two listings
FACTOR_COLS = ["mkt_rf", "smb", "hml", "rmw", "cma", "mom"]
MIN_CELL = 5


def exchange_of(ticker: str) -> str:
    return "CPH" if ticker.endswith(".CO") else "NYSE"


def expand(tickers: str) -> list[str]:
    out = []
    for t in (tickers or "").split(";"):
        if t:
            out += LISTINGS.get(t, [t])
    return out


class Panel:
    """Per-security arrays of dates, returns and regressors, built once from the warehouse."""

    def __init__(self, con):
        px = pl.from_arrow(
            con.sql(
                "select ticker, date, adj_close from eligible_prices order by ticker, date"
            ).arrow()
        )
        ret = px.with_columns(ret=pl.col("adj_close").pct_change().over("ticker")).drop_nulls("ret")
        fac = pl.from_arrow(con.sql("select * from factors").arrow())
        spy = ret.filter(pl.col("ticker") == "SPY").select("date", spy=pl.col("ret"))
        self.sec: dict[str, dict] = {}
        for tk, df in ret.group_by("ticker", maintain_order=True):
            d = df.join(fac, on="date", how="left").join(spy, on="date", how="left").sort("date")
            r = d["ret"].to_numpy()
            rf = d["rf"].to_numpy()
            ones = np.ones(len(d))
            x_ff = np.column_stack([ones] + [d[c].to_numpy() for c in FACTOR_COLS])
            x_mm = np.column_stack([ones, d["spy"].to_numpy()])
            self.sec[tk[0]] = {
                "dates": d["date"].to_list(),
                "y": {"ff6": r - rf, "mm": r},
                "x": {"ff6": x_ff, "mm": x_mm},
            }


def analyse_pair(panel: Panel, ev: dict, security: str) -> list[dict] | None:
    """Both models' CARs for one (event, security); None when the security cannot be studied."""
    s = panel.sec.get(security)
    if s is None:
        return None
    dates = s["dates"]
    try:
        f, la = ledger.day0_window(
            ev["occurred_at"], ev["timing"], ev["stated_date"], exchange_of(security), dates
        )
    except (ValueError, IndexError):
        return None
    first, last = dates.index(f), dates.index(la)
    hi = min(last + 20, len(dates) - 1)
    rows = []
    for model in ("ff6", "mm"):
        fit = es.fit_event(s["y"][model], s["x"][model], first, hi)
        if fit is None:
            continue
        row = {
            "model": model,
            "security": security,
            "first_day0": f,
            "last_day0": la,
            "ambiguous": f != la,
            "sigma": fit.sigma,
            "n_est": fit.n_est,
            "_resid": fit.resid,
        }
        for w in es.WINDOWS:
            lo_w, hi_w = es.window_bounds(first, last, w)
            car, sd, n = fit.car(lo_w, hi_w)
            full = n == hi_w - lo_w + 1  # a window cut short by the end of the data is not used
            row[f"car_{w}"] = car if full else float("nan")
            row[f"sd_{w}"] = sd if full else float("nan")
        rows.append(row)
    return rows or None


def event_table(panel: Panel, led: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    """One row per (event, security, model); also returns the estimation residuals for each row."""
    out, resids = [], {}
    for ev in led.iter_rows(named=True):
        pairs = [(sec, "own") for sec in expand(ev["ticker"])]
        pairs += [
            (sec, "read") for sec in expand(ev["also_affects"]) if sec not in expand(ev["ticker"])
        ]
        for sec, role in pairs:
            rows = analyse_pair(panel, ev, sec)
            if rows is None:
                continue
            # amendment 1: the market model stands in only when the factor model has no [-1,+1]
            have_ff = any(r["model"] == "ff6" and np.isfinite(r["car_m1p1"]) for r in rows)
            for r in rows:
                key = (ev["event_id"], sec, r["model"])
                resids[key] = r.pop("_resid")
                out.append(
                    {
                        "event_id": ev["event_id"],
                        "event_type": ev["event_type"],
                        "issuer": ev["ticker"],
                        "role": role,
                        "timing": ev["timing"],
                        "confounded": ev["confounded"],
                        "surprise": ev["surprise"],
                        "surprise_basis": ev["surprise_basis"],
                        # amendment 1: without the factor model only the market model is available
                        "primary": r["model"] == ("ff6" if have_ff else "mm"),
                        "fallback": not have_ff,
                    }
                    | r
                )
    return pl.DataFrame(out), resids


def run_cells(
    df: pl.DataFrame, resids: dict, windows=("d0", "m1p1", "p0p5", "p0p20", "drift")
) -> list[dict]:
    """Cell tests: event type x security x role, with and without confounded events."""
    cells = []
    prim = df.filter(pl.col("primary"))
    for (etype, sec, role), g in prim.group_by("event_type", "security", "role"):
        for conf_label, sub in (("clean", g.filter(~pl.col("confounded"))), ("all", g)):
            for w in windows:
                ok = sub.filter(pl.col(f"car_{w}").is_not_nan())
                if ok.height < 3:
                    continue
                res = [
                    resids[(e, sec, m)] for e, m in zip(ok["event_id"], ok["model"], strict=True)
                ]
                t = es.cell_test(ok[f"car_{w}"].to_numpy(), ok[f"sd_{w}"].to_numpy(), res)
                cells.append(
                    {
                        "event_type": etype,
                        "security": sec,
                        "role": role,
                        "sample": conf_label,
                        "window": w,
                    }
                    | t
                )
    return cells


def surprise_regressions(df: pl.DataFrame) -> list[dict]:
    """H1: CAR[-1,+1] on the surprise, own security, by basis; clean events and all events."""
    out = []
    base = df.filter(
        pl.col("primary") & (pl.col("role") == "own") & pl.col("surprise").is_not_null()
    ).filter(pl.col("car_m1p1").is_not_nan())
    base = base.with_columns(
        kind=pl.when(pl.col("surprise_basis").str.starts_with("pp weight loss"))
        .then(pl.lit("weight_loss_pp"))
        .when(pl.col("surprise_basis").str.starts_with("% change"))
        .then(pl.lit("lilly_guidance_pct"))
        .when(pl.col("surprise_basis").str.starts_with("pp change"))
        .then(pl.lit("novo_guidance_pp"))
        .otherwise(pl.lit("other"))
    )
    for sample, g in (("clean", base.filter(~pl.col("confounded"))), ("all", base)):
        # weight-loss readouts are pooled across the two sponsors (n is too small per company)
        groups = [
            (
                "weight_loss_pp",
                "LLY+NVO",
                g.filter(
                    (pl.col("kind") == "weight_loss_pp") & pl.col("security").is_in(["LLY", "NVO"])
                ),
            )
        ]
        for kind in ("lilly_guidance_pct", "novo_guidance_pp"):
            for sec in ("LLY", "NVO"):
                groups.append(
                    (kind, sec, g.filter((pl.col("kind") == kind) & (pl.col("security") == sec)))
                )
        for kind, sec, sub in groups:
            if sub.height < 6:
                continue
            x, y = sub["surprise"].to_numpy(), sub["car_m1p1"].to_numpy()
            slope, se, n = hc3_slope(x, y)
            rng = np.random.default_rng(0)
            perm = np.array([np.polyfit(rng.permutation(x), y, 1)[0] for _ in range(4999)])
            out.append(
                {
                    "sample": sample,
                    "kind": kind,
                    "security": sec,
                    "n": n,
                    "slope": slope,
                    "se_hc3": se,
                    "t": slope / se if se > 0 else float("nan"),
                    "p_perm": float((1 + np.sum(np.abs(perm) >= abs(slope))) / 5000),
                }
            )
    return out


def hc3_slope(x: np.ndarray, y: np.ndarray) -> tuple[float, float, int]:
    """OLS slope of y on x with an HC3 standard error."""
    n = len(x)
    xm = np.column_stack([np.ones(n), x])
    xtx_inv = np.linalg.inv(xm.T @ xm)
    beta = xtx_inv @ xm.T @ y
    e = y - xm @ beta
    h = np.einsum("ij,jk,ik->i", xm, xtx_inv, xm)
    meat = (xm * (e / (1 - h))[:, None]).T @ (xm * (e / (1 - h))[:, None])
    cov = xtx_inv @ meat @ xtx_inv
    return float(beta[1]), float(np.sqrt(cov[1, 1])), n


def run(paths: Paths) -> dict:
    """Run everything and write the results files."""
    con = warehouse.connect(paths)
    panel = Panel(con)
    led = ledger.load(paths)
    df, resids = event_table(panel, led)
    cells = run_cells(df, resids)
    cells_df = pl.DataFrame(cells)
    fam = cells_df.filter(
        (pl.col("window") == es.PRIMARY) & (pl.col("sample") == "clean") & (pl.col("n") >= MIN_CELL)
    )
    reject = es.benjamini_hochberg(fam["p_kp"].to_numpy(), 0.10)
    bh = [
        {
            "event_type": r["event_type"],
            "security": r["security"],
            "role": r["role"],
            "reject_bh10": bool(x),
        }
        for r, x in zip(fam.iter_rows(named=True), reject, strict=True)
    ]
    absf = cells_df.filter((pl.col("window") == es.PRIMARY) & (pl.col("n") >= MIN_CELL))
    rej_abs = es.benjamini_hochberg(absf["p_abs"].to_numpy(), 0.10)
    bh_abs = [
        {k: r[k] for k in ("event_type", "security", "role", "sample")} | {"reject_bh10": bool(x)}
        for r, x in zip(absf.iter_rows(named=True), rej_abs, strict=True)
    ]
    out = {
        "freeze_date": FREEZE_DATE.isoformat(),
        "events": led.height,
        "pairs": df.filter(pl.col("primary")).height,
        "fallback_pairs": df.filter(pl.col("primary") & pl.col("fallback")).height,
        "cells_tested_for_bh": fam.height,
        "cells": cells,
        "bh": bh,
        "bh_abs": bh_abs,
        "surprise_regressions": surprise_regressions(df),
    }
    res = paths.root / "results"
    res.mkdir(exist_ok=True)
    df.write_csv(res / "event_cars.csv")
    out["jump_model"] = jumps.summarize(res / "event_cars.csv")
    (res / "eventstudy.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    return out


if __name__ == "__main__":
    from glp1.config import get_paths

    r = run(get_paths())
    print(
        {
            k: v
            for k, v in r.items()
            if k not in ("cells", "bh", "bh_abs", "surprise_regressions", "jump_model")
        }
    )
    print(date.today())
