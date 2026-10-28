"""Forecast engine: predictive distributions of the log return, scored against baselines.

Models (methodology section 6): B0 random walk with trailing volatility; B1 GJR-GARCH(1,1) with
Student-t errors; B2 filtered historical simulation (GARCH with bootstrapped standardised
residuals); M1 jump-diffusion (GARCH fitted on returns with news-day jumps clipped, plus scheduled
earnings jumps and compound-Poisson unscheduled jumps whose sizes come only from ledger events
already in the past); M2 M1 with adaptive conformal calibration of the interval width (Gibbs and
Candes 2021).
Every forecast is 99 quantiles of the h-day log return. Nothing here is a trading signal.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import polars as pl
from arch import arch_model
from scipy import stats

HORIZONS = (1, 5, 21, 63, 126, 252)
LEVELS = np.arange(1, 100) / 100
SIMS = 2000
PRIOR_JUMP_SD, PRIOR_WEIGHT = 0.06, 5
SCHEDULED_GAP = 91  # days between quarterly reports


def crps_from_quantiles(q: np.ndarray, y: float) -> float:
    """CRPS as twice the mean pinball loss over the 99 quantile levels."""
    d = y - q
    return float(2 * np.mean(np.maximum(LEVELS * d, (LEVELS - 1) * d)))


# ── baselines ────────────────────────────────────────────────────────────────


def b0(r: np.ndarray) -> dict[int, np.ndarray]:
    """Random walk: zero drift, trailing 252-day volatility, normal quantiles."""
    sd = float(np.std(r[-252:], ddof=1))
    z = stats.norm.ppf(LEVELS)
    return {h: sd * np.sqrt(h) * z for h in HORIZONS}


def _fit(r: np.ndarray):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        am = arch_model(r * 100, mean="Zero", vol="GARCH", p=1, o=1, q=1, dist="t")
        return am.fit(disp="off", options={"maxiter": 300})


def _paths(res, method: str, seed: int) -> np.ndarray:
    """Simulated cumulative log returns, shape (SIMS, max horizon), in decimal units.

    GJR-GARCH(1,1) recursion from the last fitted state. ``simulation`` draws standardised
    Student-t shocks with the fitted degrees of freedom; ``bootstrap`` resamples the fitted
    standardised residuals (filtered historical simulation).
    """
    rng = np.random.default_rng(seed)
    p = res.params
    mu, omega, alpha, gamma, beta = (
        0.0,
        p["omega"],
        p["alpha[1]"],
        p["gamma[1]"],
        p["beta[1]"],
    )
    horizon = max(HORIZONS)
    if method == "bootstrap":
        pool = np.asarray(res.std_resid)
        pool = pool[np.isfinite(pool)]
        z = rng.choice(pool, size=(SIMS, horizon))
    else:
        nu = float(p["nu"])
        z = rng.standard_t(nu, size=(SIMS, horizon)) * np.sqrt((nu - 2) / nu)
    eps = np.full(SIMS, float(np.asarray(res.resid)[-1]))
    var = np.full(SIMS, float(np.asarray(res.conditional_volatility)[-1]) ** 2)
    out = np.empty((SIMS, horizon))
    for t in range(horizon):
        var = omega + (alpha + gamma * (eps < 0)) * eps**2 + beta * var
        eps = np.sqrt(var) * z[:, t]
        out[:, t] = mu + eps
    return np.cumsum(out, axis=1) / 100


def _quantiles(paths: np.ndarray) -> dict[int, np.ndarray]:
    return {h: np.quantile(paths[:, h - 1], LEVELS) for h in HORIZONS}


def b1_b2(r: np.ndarray) -> tuple[dict, dict]:
    res = _fit(r)
    return _quantiles(_paths(res, "simulation", 0)), _quantiles(_paths(res, "bootstrap", 0))


# ── jump-diffusion ───────────────────────────────────────────────────────────


@dataclass
class JumpInputs:
    sched_sd: float  # standard deviation of a scheduled (earnings) jump
    unsched_sd: float
    unsched_rate: float  # unscheduled jumps per trading year
    last_report: date | None


def jump_inputs(events: pl.DataFrame, origin: date) -> JumpInputs:
    """Jump parameters from ledger events fully observed before the origin (no look-ahead).

    ``events`` has one row per own event: event_type, last_day0, car_m1p1, sd_m1p1.
    """
    past = events.filter(pl.col("last_day0") + pl.duration(days=2) < origin)

    def sd(df: pl.DataFrame) -> float:
        n = df.height
        if n == 0:
            return PRIOR_JUMP_SD
        excess = max(
            float(np.mean(df["car_m1p1"].to_numpy() ** 2 - df["sd_m1p1"].to_numpy() ** 2)), 0
        )
        return float(np.sqrt((n * excess + PRIOR_WEIGHT * PRIOR_JUMP_SD**2) / (n + PRIOR_WEIGHT)))

    sched = past.filter(pl.col("event_type") == "earnings_guidance")
    unsched = past.filter(pl.col("event_type") != "earnings_guidance")
    first = events["last_day0"].min()
    years = max((origin - first).days / 365.25, 1.0)
    last = sched["last_day0"].max() if sched.height else None
    return JumpInputs(sd(sched), sd(unsched), unsched.height / years, last)


def n_scheduled(inp: JumpInputs, origin: date, h: int) -> int:
    """Reports expected in the next h trading days, projected from the last one (every ~91 days)."""
    if inp.last_report is None:
        return 0
    horizon_end = origin + timedelta(days=int(h * 365.25 / 252))
    nxt = inp.last_report
    n = 0
    while True:
        nxt = nxt + timedelta(days=SCHEDULED_GAP)
        if nxt > horizon_end:
            return n
        if nxt > origin:
            n += 1


def clip_event_days(r: np.ndarray, is_event: np.ndarray) -> np.ndarray:
    """Clip news-day returns to 2.5 trailing standard deviations so GARCH is not fitted to jumps."""
    out = r.copy()
    sd = np.sqrt(
        np.convolve(np.r_[np.full(60, np.var(r[:60])), r**2], np.ones(60) / 60, "valid")[: len(r)]
    )
    cap = 2.5 * sd
    hit = is_event & (np.abs(r) > cap)
    out[hit] = np.sign(r[hit]) * cap[hit]
    return out


def m1(r: np.ndarray, is_event: np.ndarray, inp: JumpInputs, origin: date, seed: int) -> dict:
    res = _fit(clip_event_days(r, is_event))
    paths = _paths(res, "simulation", seed)
    rng = np.random.default_rng(seed)
    out = {}
    for h in HORIZONS:
        k = n_scheduled(inp, origin, h)
        jumps = rng.normal(0, inp.sched_sd, (SIMS, k)).sum(axis=1) if k else np.zeros(SIMS)
        nu = rng.poisson(inp.unsched_rate * h / 252, SIMS)
        jumps = jumps + rng.normal(0, 1, SIMS) * inp.unsched_sd * np.sqrt(nu)
        out[h] = np.quantile(paths[:, h - 1] + jumps, LEVELS)
    return out


# ── adaptive conformal calibration ───────────────────────────────────────────


class AdaptiveConformal:
    """Per-(security, horizon) calibration of the predictive width (Gibbs and Candes 2021).

    Score s = |y - median| / half-width of the model's 80% interval, so s <= 1 for 80% of outcomes
    when the model is calibrated. The width multiplier applied to a new forecast is the
    (1 - alpha_t) quantile of the scores whose outcomes are already known; alpha_t falls after a
    miss and rises after a hit, so the realised miss rate is pulled to alpha whatever the regime.
    """

    def __init__(self, alpha: float = 0.2, gamma: float = 0.02, min_scores: int = 20):
        self.alpha, self.gamma, self.min_scores = alpha, gamma, min_scores
        self.alpha_t = alpha
        self.scores: list[float] = []

    def scale(self) -> float:
        if len(self.scores) < self.min_scores:
            return 1.0
        level = min(max(1 - self.alpha_t, 0.5), 0.995)
        return float(np.quantile(self.scores, level))

    def adjust(self, q: np.ndarray, k: float | None = None) -> np.ndarray:
        med = q[49]
        return med + (q - med) * (self.scale() if k is None else k)

    def observe(self, q: np.ndarray, y: float, k_used: float) -> None:
        half = max((q[89] - q[9]) / 2, 1e-12)
        s = abs(y - q[49]) / half
        miss = float(s > k_used)
        self.alpha_t += self.gamma * (self.alpha - miss)
        self.scores.append(s)


# ── backtest ─────────────────────────────────────────────────────────────────

DEV_START, DEV_END, TEST_START = date(2021, 1, 4), date(2025, 10, 31), date(2025, 11, 3)
TRAIN_START = date(2018, 1, 2)
MODELS = ("B0", "B1", "B2", "M1", "M2")


def load_returns(con, ticker: str) -> pl.DataFrame:
    return (
        pl.from_arrow(
            con.sql(
                f"select date, adj_close from eligible_prices where ticker='{ticker}' order by date"
            ).arrow()
        )
        .with_columns(r=pl.col("adj_close").log().diff())
        .drop_nulls("r")
    )


def event_frame(cars: pl.DataFrame, ticker: str) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(own events with CARs, all event windows touching this security)."""
    d = cars.filter(
        pl.col("primary") & (pl.col("security") == ticker) & pl.col("car_m1p1").is_not_nan()
    ).with_columns(pl.col("first_day0").str.to_date(), pl.col("last_day0").str.to_date())
    own = d.filter(pl.col("role") == "own").unique(["first_day0", "event_type"])
    return own.select("event_type", "last_day0", "car_m1p1", "sd_m1p1"), d.select(
        "first_day0", "last_day0"
    )


def origins(dates: list[date]) -> list[int]:
    """Index of the first trading day of every week between DEV_START and the last date."""
    out, seen = [], set()
    for i, d in enumerate(dates):
        wk = d.isocalendar()[:2]
        if d >= DEV_START and wk not in seen:
            seen.add(wk)
            out.append(i)
    return out


def run_security(con, cars: pl.DataFrame, ticker: str, log=print) -> list[dict]:
    px = load_returns(con, ticker).filter(pl.col("date") >= TRAIN_START)
    dates, r = px["date"].to_list(), px["r"].to_numpy()
    lp = np.cumsum(r)  # log price relative to the first date
    own, windows = event_frame(cars, ticker)
    is_event = np.zeros(len(dates), bool)
    for f, la in windows.iter_rows():
        is_event |= np.array([f <= d <= la for d in dates])
    ac = {h: AdaptiveConformal() for h in HORIZONS}
    pending: list[tuple[int, int, np.ndarray, float]] = []  # (due index, h, q, k_used)
    rows = []
    for n, i in enumerate(origins(dates)):
        # outcomes that became known by this origin update the calibrators
        done = [p for p in pending if p[0] <= i]
        pending = [p for p in pending if p[0] > i]
        for due, h, q, k in sorted(done, key=lambda x: x[0]):
            ac[h].observe(q, lp[due] - lp[due - h], k)
        origin = dates[i]
        hist, ev = r[: i + 1], is_event[: i + 1]
        inp = jump_inputs(own, origin)
        fc = {"B0": b0(hist)}
        fc["B1"], fc["B2"] = b1_b2(hist)
        fc["M1"] = m1(hist, ev, inp, origin, seed=n)
        fc["M2"] = {}
        for h in HORIZONS:
            k = ac[h].scale()
            fc["M2"][h] = ac[h].adjust(fc["M1"][h], k)
            if i + h < len(dates):
                pending.append((i + h, h, fc["M1"][h], k))
        for h in HORIZONS:
            y = float(lp[i + h] - lp[i]) if i + h < len(dates) else float("nan")
            for m in MODELS:
                rows.append(
                    {
                        "ticker": ticker,
                        "origin": origin,
                        "h": h,
                        "model": m,
                        "y": y,
                        "q": fc[m][h].tolist(),
                        "catalyst_soon": n_scheduled(inp, origin, 21) > 0,
                    }
                )
        if n % 20 == 0:
            log(f"{ticker} origin {origin} ({n})")
    return rows


# ── scoring ──────────────────────────────────────────────────────────────────

BASELINES = ("B0", "B1", "B2")
IDX = {5: 4, 25: 24, 50: 49, 75: 74, 95: 94}


def pinball(q: np.ndarray, y: float, tau: int) -> float:
    d = y - q[IDX[tau]]
    return float(max(tau / 100 * d, (tau / 100 - 1) * d))


def dm_one_sided(loss_base: np.ndarray, loss_model: np.ndarray, h: int) -> tuple[float, float]:
    """Diebold-Mariano with Harvey's small-sample correction; p-value for 'model is better'.

    Origins are a week apart, so an h-day target overlaps ceil(h / 5) neighbours: the Newey-West
    bandwidth is that number minus one (the protocol's h - 1 trading days, in weekly steps).
    """
    d = np.asarray(loss_base) - np.asarray(loss_model)
    n = len(d)
    if n < 10:
        return float("nan"), float("nan")
    k = max(int(np.ceil(h / 5)) - 1, 0)
    dm = d - d.mean()
    lrv = dm @ dm / n
    for j in range(1, k + 1):
        lrv += 2 * (1 - j / (k + 1)) * (dm[j:] @ dm[:-j]) / n
    stat = d.mean() / np.sqrt(max(lrv, 1e-18) / n)
    stat *= np.sqrt((n + 1 - 2 * (k + 1) + (k + 1) * k / n) / n)  # Harvey, Leybourne, Newbold
    return float(stat), float(stats.t.sf(stat, n - 1))


def score(fc: pl.DataFrame) -> dict:
    """Mean CRPS, coverage and pinball by cell, and the decision-rule comparisons."""
    fc = fc.filter(pl.col("y").is_not_nan()).with_columns(
        period=pl.when(pl.col("origin") <= DEV_END).then(pl.lit("dev")).otherwise(pl.lit("test"))
    )
    recs = []
    for row in fc.iter_rows(named=True):
        q, y = np.asarray(row["q"]), row["y"]
        rec = {k: row[k] for k in ("ticker", "origin", "h", "model", "period", "catalyst_soon")}
        rec["crps"] = crps_from_quantiles(q, y)
        for lo, hi, name in ((24, 74, "c50"), (9, 89, "c80"), (4, 94, "c90")):
            rec[name] = float(q[lo] <= y <= q[hi])
        for tau in IDX:
            rec[f"pin{tau}"] = pinball(q, y, tau)
        recs.append(rec)
    df = pl.DataFrame(recs)
    cells = (
        df.group_by("ticker", "h", "model", "period")
        .agg(
            n=pl.len(),
            crps=pl.col("crps").mean(),
            c50=pl.col("c50").mean(),
            c80=pl.col("c80").mean(),
            c90=pl.col("c90").mean(),
            pin5=pl.col("pin5").mean(),
            pin50=pl.col("pin50").mean(),
            pin95=pl.col("pin95").mean(),
        )
        .sort("ticker", "h", "model", "period")
    )
    comps = []
    for (tk, h), g in df.group_by("ticker", "h"):
        dev = g.filter(pl.col("period") == "dev")
        best = (
            dev.filter(pl.col("model").is_in(BASELINES))
            .group_by("model")
            .agg(pl.col("crps").mean())
            .sort("crps")["model"][0]
        )
        for m in ("M1", "M2"):
            res = {"ticker": tk, "h": h, "model": m, "best_baseline": best}
            for per in ("dev", "test"):
                for subset in ("all", "catalyst"):
                    sub = g.filter(pl.col("period") == per)
                    if subset == "catalyst":
                        sub = sub.filter(pl.col("catalyst_soon"))
                    a = sub.filter(pl.col("model") == best).sort("origin")
                    b = sub.filter(pl.col("model") == m).sort("origin")
                    stat, p = dm_one_sided(a["crps"].to_numpy(), b["crps"].to_numpy(), h)
                    res[f"{per}_{subset}_n"] = b.height
                    res[f"{per}_{subset}_crps_base"] = float(a["crps"].mean()) if a.height else None
                    res[f"{per}_{subset}_crps_model"] = (
                        float(b["crps"].mean()) if b.height else None
                    )
                    res[f"{per}_{subset}_dm"] = stat
                    res[f"{per}_{subset}_p"] = p
            res["beats"] = bool(
                res["dev_all_crps_model"] is not None
                and res["dev_all_crps_model"] < res["dev_all_crps_base"]
                and res["dev_all_p"] < 0.10
                and (res["test_all_crps_model"] or 9) < (res["test_all_crps_base"] or 0)
            )
            comps.append(res)
    return {"cells": cells.to_dicts(), "comparisons": comps}


def run(paths, log=print) -> dict:
    import json

    from glp1 import warehouse

    con = warehouse.connect(paths)
    cars = pl.read_csv(paths.root / "results" / "event_cars.csv")
    rows = []
    for tk in ("LLY", "NVO"):
        rows += run_security(con, cars, tk, log)
    fc = pl.DataFrame(rows)
    fc.write_parquet(paths.processed / "forecast_quantiles.parquet")
    out = score(fc)
    d = paths.root / "results"
    d.mkdir(exist_ok=True)
    (d / "forecast_scores.json").write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8"
    )
    return out
