"""The nightly run: fresh prices, a new forecast, the public forecast ledger and its scorecard.

Output goes to ``site/public/data`` (read by the live page) and ``forecasts/`` (the append-only
ledger and the conformal state), both committed by the GitHub Action. A forecast is written once and
never edited: each ledger line carries the SHA-256 of the previous line, so a rewrite of history
shows. Nothing here is a trading signal.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, date, datetime, timedelta
from datetime import time as clock
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import numpy as np
import polars as pl

from glp1 import forecast as fc
from glp1 import kalshi, ledger
from glp1.config import Paths
from glp1.ingest import yahoo
from glp1.universe import BY_TICKER

LIVE = ("LLY", "NVO")
SIGMA_GRID = [1, 2, 3, 5, 10, 15, 21, 30, 42, 63, 84, 105, 126, 168, 210, 252]
TRADING_PER_YEAR = 252
LIVE_GAMMA = 0.02 / 5  # the backtest stepped weekly, the live ledger steps daily
GENESIS = "0" * 64


def data_dir(paths: Paths) -> Path:
    d = paths.root / "site" / "public" / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ledger_path(paths: Paths) -> Path:
    d = paths.root / "forecasts"
    d.mkdir(exist_ok=True)
    return d / "ledger.jsonl"


# ── prices ───────────────────────────────────────────────────────────────────


def drop_open_session(df: pl.DataFrame, now: datetime) -> pl.DataFrame:
    """Drop today's bar until 16:30 ET (while the market is open Yahoo serves it unfinished)."""
    et = now.astimezone(ZoneInfo("America/New_York"))
    if df.height and df["date"][-1] == et.date() and (et.hour, et.minute) < (16, 30):
        return df.slice(0, df.height - 1)
    return df


def fresh_prices(paths: Paths, ticker: str, now: datetime) -> pl.DataFrame:
    for attempt in range(3):  # runner IPs are sometimes throttled; an origin cannot be backfilled
        try:
            with httpx.Client(headers={"User-Agent": yahoo.USER_AGENT}, timeout=30) as client:
                ok = yahoo.fetch(paths, BY_TICKER[ticker], now.date() + timedelta(days=1), client)
            break
        except httpx.HTTPError:
            if attempt == 2:
                raise
            time.sleep(10 * (attempt + 1))
    got = yahoo.load_cached(paths, ticker) if ok else None
    if got is None:
        raise RuntimeError(f"no prices for {ticker}")
    return drop_open_session(got[0].sort("date").drop_nulls(["close", "adj_close"]), now)


# ── catalysts and scenario inputs ────────────────────────────────────────────


def earnings_outcomes(cars: pl.DataFrame, ticker: str, sched_sd: float | None = None) -> list[dict]:
    """How the stock moved on earnings days where guidance was raised, kept or cut (own history).

    Means are centred on the average report (the event study found no average earnings-day move) and
    the spreads are scaled so the mix has the same variance as the model's own earnings jump.
    """
    d = cars.filter(
        pl.col("primary")
        & (pl.col("role") == "own")
        & (pl.col("security") == ticker)
        & (pl.col("event_type") == "earnings_guidance")
        & pl.col("surprise").is_not_null()
        & pl.col("car_m1p1").is_not_nan()
    ).with_columns(
        label=pl.when(pl.col("surprise") > 0)
        .then(pl.lit("guidance raised"))
        .when(pl.col("surprise") < 0)
        .then(pl.lit("guidance cut"))
        .otherwise(pl.lit("guidance unchanged"))
    )
    total = d.height
    out = []
    for label in ("guidance raised", "guidance unchanged", "guidance cut"):
        g = d.filter(pl.col("label") == label)
        if g.height == 0:
            continue
        sd = float(g["car_m1p1"].std()) if g.height > 2 else float(d["car_m1p1"].std())
        out.append(
            {
                "label": label,
                "n": g.height,
                "probability": round(g.height / total, 4),
                "raw_mean": round(float(g["car_m1p1"].mean()), 4),
                "sd": sd,
            }
        )
    mix = sum(o["probability"] * o["raw_mean"] for o in out)
    between = sum(o["probability"] * (o["raw_mean"] - mix) ** 2 for o in out)
    within = sum(o["probability"] * o["sd"] ** 2 for o in out)
    scale = 1.0
    if sched_sd:
        scale = min(1.0, max(0.3, np.sqrt(max(sched_sd**2 - between, 0.1 * sched_sd**2) / within)))
    for o in out:
        o["mean"] = round(o["raw_mean"] - mix, 4)
        o["sd"] = round(o["sd"] * scale, 4)
    return out


def catalyst_list(
    cal: pl.DataFrame,
    ticker: str,
    today: date,
    cars: pl.DataFrame,
    markets: list[dict],
    sched_sd: float | None = None,
) -> list[dict]:
    """Upcoming modelled catalysts for one stock with default outcome probabilities."""
    out = []
    for r in cal.filter(pl.col("ticker") == ticker).iter_rows(named=True):
        end = r["window_end"]
        if end < today:
            continue
        if r["event_type"] == "earnings_guidance" and r["window_start"] <= today:
            continue  # a report on or before the origin is already in the price
        item = {
            "id": r["catalyst_id"],
            "title": r["title"],
            "type": r["event_type"],
            "window_start": str(r["window_start"]),
            "window_end": str(r["window_end"]),
            "offset": max(offset(r["window_start"] + (end - r["window_start"]) / 2, today), 1),
            "source": r["source_url"],
        }
        if r["event_type"] == "earnings_guidance":
            item["model"] = "earnings"
            item["outcomes"] = earnings_outcomes(cars, ticker, sched_sd)
        elif "cagrisema" in r["title"].lower() or "FDA decision" in r["title"]:
            item["model"] = "approval"
            soon = [m for m in markets if m["probability"] is not None]
            before = [m for m in soon if m["closes"][:10] >= str(r["window_end"])]
            if before:
                m = before[0]
                item["market"] = {k: m[k] for k in ("ticker", "title", "closes", "probability")}
        else:
            item["model"] = "info"
        out.append(item)
    return out


# ── forecast ─────────────────────────────────────────────────────────────────


def seed_for(day: date, ticker: str) -> int:
    return int(hashlib.sha256(f"{day}{ticker}".encode()).hexdigest()[:8], 16)


def load_aci(paths: Paths) -> dict:
    f = paths.root / "forecasts" / "aci_state.json"
    state = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    out = {}
    for tk in LIVE:
        out[tk] = {}
        for h in fc.HORIZONS:
            ac = fc.AdaptiveConformal(gamma=LIVE_GAMMA)
            s = state.get(tk, {}).get(str(h))
            if s:
                ac.alpha_t, ac.scores = s["alpha_t"], list(s["scores"])
            out[tk][h] = ac
    return out


def seed_aci(paths: Paths) -> None:
    """Start the live conformal state from the backtest's calibrators (run once, locally)."""
    from glp1 import warehouse

    con = warehouse.connect(paths)
    cars = pl.read_csv(paths.root / "results" / "event_cars.csv")
    aci = {}
    for tk in LIVE:
        aci[tk] = {}
        fc.run_security(con, cars, tk, final=aci[tk])
    (paths.root / "forecasts").mkdir(exist_ok=True)
    save_aci(paths, aci)
    save_scored(paths, set())  # the seeded state has seen no live outcome


def save_aci(paths: Paths, aci: dict) -> None:
    state = {
        tk: {str(h): {"alpha_t": ac.alpha_t, "scores": ac.scores} for h, ac in hs.items()}
        for tk, hs in aci.items()
    }
    (paths.root / "forecasts" / "aci_state.json").write_text(json.dumps(state), encoding="utf-8")


def offset(day: date, origin: date) -> int:
    """Weekdays from the origin to a calendar day (US holidays are not subtracted)."""
    return int(np.busday_count(origin, day))


def sched_offsets(inp: fc.JumpInputs, origin: date) -> list[int]:
    """Trading-day offsets of the reports the jump model expects within a year."""
    out, nxt = [], inp.last_report
    while nxt is not None:
        nxt = nxt + timedelta(days=fc.SCHEDULED_GAP)
        if offset(nxt, origin) > TRADING_PER_YEAR:
            return out
        if nxt > origin:
            out.append(offset(nxt, origin))
    return out


def next_report(cal: pl.DataFrame, ticker: str, origin: date) -> date | None:
    d = cal.filter(
        (pl.col("ticker") == ticker)
        & (pl.col("event_type") == "earnings_guidance")
        & (pl.col("window_start") > origin)
    )
    return d["window_start"].min() if d.height else None


def forecast_one(
    ticker: str, px: pl.DataFrame, cars: pl.DataFrame, cal: pl.DataFrame, aci: dict
) -> dict:
    r_df = (
        px.filter(pl.col("date") >= fc.TRAIN_START)
        .with_columns(r=pl.col("adj_close").log().diff())
        .drop_nulls("r")
    )
    dates, r = r_df["date"].to_list(), r_df["r"].to_numpy()
    own, windows = fc.event_frame(cars, ticker)
    is_event = np.zeros(len(dates), bool)
    for f, la in windows.iter_rows():
        is_event |= np.array([f <= d <= la for d in dates])
    origin = dates[-1]
    inp = fc.jump_inputs(own, origin)
    nxt = next_report(cal, ticker, origin)
    if nxt:  # known report date beats the 91-day projection
        inp.last_report = nxt - timedelta(days=fc.SCHEDULED_GAP)
    res = fc._fit(fc.clip_event_days(r, is_event))
    paths_ = fc._paths(res, "simulation", seed_for(origin, ticker))
    sd_grid = {h: float(np.std(paths_[:, h - 1])) for h in SIGMA_GRID}
    offsets = sched_offsets(inp, origin)
    m1 = fc.m1(
        r, is_event, inp, origin, seed_for(origin, ticker), lambda h: sum(o <= h for o in offsets)
    )
    spot = float(px["close"][-1])
    out = {
        "ticker": ticker,
        "origin": str(origin),
        "spot": spot,
        "nu": float(res.params["nu"]),
        "diffusion_sd": {str(h): v for h, v in sd_grid.items()},
        "diffusion_q": {
            str(h): [round(float(x), 5) for x in np.quantile(paths_[:, h - 1], fc.LEVELS)]
            for h in SIGMA_GRID
        },
        "sched_offsets": offsets,
        "jumps": {
            "scheduled_sd": inp.sched_sd,
            "unscheduled_sd": inp.unsched_sd,
            "unscheduled_per_year": inp.unsched_rate,
            "last_report": str(inp.last_report),
        },
        "m1": {str(h): [round(float(x), 5) for x in q] for h, q in m1.items()},
        "m2": {},
        "k": {},
    }
    for h, q in m1.items():
        k = aci[ticker][h].scale()
        out["k"][str(h)] = k
        out["m2"][str(h)] = [round(float(x), 5) for x in aci[ticker][h].adjust(q, k)]
    return out


# ── ledger ───────────────────────────────────────────────────────────────────


def read_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = []
    for i, x in enumerate(lines):
        try:
            rows.append(json.loads(x))
        except json.JSONDecodeError:
            if i < len(lines) - 1:  # only a torn last line (a crashed write) is forgiven
                raise
    return rows


def entry_hash(prev: str, body: dict) -> str:
    return hashlib.sha256(
        (prev + json.dumps(body, sort_keys=True, separators=(",", ":"))).encode()
    ).hexdigest()


def append_ledger(path: Path, forecasts: list[dict], made_at: str) -> int:
    """Append one line per (ticker, origin) not yet in the ledger; return how many were added."""
    rows = read_ledger(path)
    have = {(x["body"]["ticker"], x["body"]["origin"]) for x in rows}
    prev = rows[-1]["hash"] if rows else GENESIS
    added = 0
    with path.open("a", encoding="utf-8", newline="\n") as f:
        for fcast in forecasts:
            key = (fcast["ticker"], fcast["origin"])
            if key in have:
                continue
            body = {
                "ticker": fcast["ticker"],
                "origin": fcast["origin"],
                "made_at": made_at,
                "spot": fcast["spot"],
                "model": "M2",
                "horizons": fc.HORIZONS,
                "m1": fcast["m1"],
                "k": fcast["k"],
                "m2": fcast["m2"],
            }
            h = entry_hash(prev, body)
            line = {"prev": prev, "hash": h, "body": body}
            f.write(json.dumps(line, separators=(",", ":"), allow_nan=False) + "\n")
            prev, added = h, added + 1
    return added


def verify_ledger(path: Path) -> bool:
    """True when every line's hash matches its body and the previous line."""
    prev = GENESIS
    for row in read_ledger(path):
        if row["prev"] != prev or row["hash"] != entry_hash(prev, row["body"]):
            return False
        prev = row["hash"]
    return True


def made_after_close(made_at: str, day: date) -> bool:
    """True when the forecast was written after the close of ``day`` (its outcome was public)."""
    et = ZoneInfo("America/New_York")
    return datetime.fromisoformat(made_at).astimezone(et) >= datetime.combine(day, clock(16), et)


def score_ledger(path: Path, prices: dict[str, pl.DataFrame], aci: dict, done: set[str]) -> dict:
    """Score matured entries and feed their outcomes to the conformal state exactly once.

    An entry written after its outcome was public (a late run) stays in the ledger but is neither
    scored nor fed to the calibrator.
    """
    rows = []
    for row in read_ledger(path):
        b = row["body"]
        px = prices[b["ticker"]].sort("date")
        dates = px["date"].to_list()
        origin = date.fromisoformat(b["origin"])
        if origin not in dates:
            continue
        i = dates.index(origin)
        lp = px["adj_close"].log().to_numpy()
        for h in b["horizons"]:
            key = f"{b['ticker']}|{b['origin']}|{h}"
            if i + h >= len(dates):
                continue
            if made_after_close(b["made_at"], dates[i + h]):
                done.add(key)
                continue
            y = float(lp[i + h] - lp[i])
            q2, q1 = np.asarray(b["m2"][str(h)]), np.asarray(b["m1"][str(h)])
            rows.append(
                {
                    "ticker": b["ticker"],
                    "origin": b["origin"],
                    "h": h,
                    "resolved": str(dates[i + h]),
                    "crps": fc.crps_from_quantiles(q2, y),
                    "in80": bool(q2[9] <= y <= q2[89]),
                    "in90": bool(q2[4] <= y <= q2[94]),
                    "y": y,
                }
            )
            if key not in done:
                aci[b["ticker"]][h].observe(q1, y, b["k"][str(h)])
                done.add(key)
    summary = []
    if rows:
        for (tk, h), g in pl.DataFrame(rows).group_by("ticker", "h"):
            summary.append(
                {
                    "ticker": tk,
                    "h": h,
                    "n": g.height,
                    "mean_crps": float(g["crps"].mean()),
                    "coverage80": float(g["in80"].mean()),
                    "coverage90": float(g["in90"].mean()),
                }
            )
    return {
        "resolved": rows[-200:],
        "summary": sorted(summary, key=lambda x: (x["ticker"], x["h"])),
    }


def load_scored(paths: Paths) -> set[str]:
    f = paths.root / "forecasts" / "scored.json"
    return set(json.loads(f.read_text(encoding="utf-8"))) if f.exists() else set()


def save_scored(paths: Paths, done: set[str]) -> None:
    f = paths.root / "forecasts" / "scored.json"
    f.write_text(json.dumps(sorted(done)), encoding="utf-8")


# ── driver ───────────────────────────────────────────────────────────────────


def site_data(paths: Paths, out: Path) -> None:
    """Static summaries the page shows next to the forecast: events, valuation, backtest."""
    cars = pl.read_csv(paths.root / "results" / "event_cars.csv")
    titles = pl.read_csv(paths.root / "data" / "ledger" / "catalysts.csv").select(
        "event_id", "title", "stated_date", "ticker"
    )
    ev = (
        cars.filter(
            pl.col("primary")
            & (pl.col("role") == "own")
            & pl.col("car_m1p1").is_not_nan()
            & (pl.col("security") != "NOVO-B.CO")  # cross-check listing of the same news as NVO
        )
        .join(titles, on="event_id", how="left", suffix="_l")
        .unique(["event_id", "security"])
        .sort("first_day0")
        .select(
            "event_id",
            "security",
            "event_type",
            "title",
            "first_day0",
            "car_m1p1",
            "sd_m1p1",
            "confounded",
            "surprise",
        )
    )
    (out / "events.json").write_text(json.dumps(ev.to_dicts()), encoding="utf-8")
    val = json.loads((paths.root / "results" / "valuation.json").read_text(encoding="utf-8"))
    weekly = [
        {k: w[k] for k in ("date", "ev_bn", "glp1_ttm_bn")} | {"peak": w["peak_c"]}
        for w in val["weekly"]
    ]
    (out / "valuation.json").write_text(
        json.dumps(
            {
                "latest": val["latest"],
                "weekly": weekly,
                "news": val["news_day_attribution"],
                "grid": val["assumption_grid"],
            }
        ),
        encoding="utf-8",
    )
    sc = json.loads((paths.root / "results" / "forecast_scores.json").read_text(encoding="utf-8"))
    cells = [
        {k: c[k] for k in ("ticker", "h", "model", "period", "n", "crps", "c80")}
        for c in sc["cells"]
    ]
    (out / "backtest.json").write_text(json.dumps(cells), encoding="utf-8")


def run(paths: Paths, now: datetime | None = None, markets: list[dict] | None = None) -> dict:
    now = now or datetime.now(UTC)
    cars = pl.read_csv(paths.root / "results" / "event_cars.csv")
    cal = ledger.load_forward(paths)
    prices = {tk: fresh_prices(paths, tk, now) for tk in LIVE}
    aci = load_aci(paths)
    done = load_scored(paths)
    scorecard = score_ledger(ledger_path(paths), prices, aci, done)
    if markets is None:
        try:
            markets = kalshi.fetch()
        except (httpx.HTTPError, KeyError, ValueError):
            markets = []  # an outage must not cost the day's forecast
    forecasts = []
    for tk in LIVE:
        f = forecast_one(tk, prices[tk], cars, cal, aci)
        f["catalysts"] = catalyst_list(
            cal, tk, date.fromisoformat(f["origin"]), cars, markets, f["jumps"]["scheduled_sd"]
        )
        f["history"] = [
            {"date": str(d), "close": round(c, 2)}
            for d, c in zip(prices[tk]["date"][-300:], prices[tk]["close"][-300:], strict=True)
        ]
        forecasts.append(f)
    added = append_ledger(ledger_path(paths), forecasts, now.isoformat(timespec="seconds"))
    save_aci(paths, aci)
    save_scored(paths, done)  # together with the calibrator: one without the other double counts
    out = data_dir(paths)
    (out / "forecast.json").write_text(
        json.dumps(
            {
                "generated": now.isoformat(timespec="seconds"),
                "stocks": forecasts,
                "kalshi": markets,
            },
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    site_data(paths, out)
    (out / "scorecard.json").write_text(json.dumps(scorecard), encoding="utf-8")
    return {
        "ledger_added": added,
        "ledger_ok": verify_ledger(ledger_path(paths)),
        "origins": [f["origin"] for f in forecasts],
    }
