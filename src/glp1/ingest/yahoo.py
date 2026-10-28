"""Daily prices from Yahoo Finance's chart endpoint.

Fetching and parsing are separate so the parser is tested offline. Yahoo is an unofficial source,
so the raw JSON is kept exactly as received (and logged in the manifest) and every later step
reads that cache, never the network.

Two traps found while probing: ``range=max`` returns a silently downsampled series, so an explicit
``period1``/``period2`` is always used; and a delisted ticker answers HTTP 404 with a JSON error,
which is recorded as missing rather than raised.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import polars as pl

from glp1.config import Paths
from glp1.ingest import manifest
from glp1.universe import DATA_START, Security

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
USER_AGENT = "glp1-market-lab/0.1 (https://github.com/deadmigue55/glp1-market-lab)"

PRICE_SCHEMA = {
    "ticker": pl.String,
    "date": pl.Date,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "adj_close": pl.Float64,
    "volume": pl.Float64,
}
ACTION_SCHEMA = {"ticker": pl.String, "date": pl.Date, "kind": pl.String, "value": pl.Float64}


def raw_path(paths: Paths, ticker: str) -> Path:
    """Where the raw JSON for one ticker is cached (``=`` is not a safe file-name character)."""
    return paths.raw / "yahoo" / f"{ticker.replace('=', '_')}.json"


def _epoch(day: str) -> int:
    return int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp())


def fetch(paths: Paths, sec: Security, end: date, client: httpx.Client | None = None) -> bool:
    """Download one ticker into the raw cache. Returns False when Yahoo has no data for it."""
    url = URL.format(ticker=sec.ticker)
    params = {
        "period1": _epoch(DATA_START),
        "period2": _epoch(end.isoformat()) + 86400,
        "interval": "1d",
        "events": "div,split",
    }
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30)
    try:
        r = client.get(url, params=params)
    finally:
        if own:
            client.close()
    out = raw_path(paths, sec.ticker)
    if r.status_code == 404 or (r.status_code == 200 and not r.json()["chart"]["result"]):
        manifest.record(paths, "yahoo", sec.ticker, str(r.url), "missing", b"", None)
        return False
    r.raise_for_status()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(r.content)
    manifest.record(paths, "yahoo", sec.ticker, str(r.url), "ok", r.content, out)
    return True


def parse(ticker: str, payload: dict) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Turn a chart response into (prices, corporate actions), dated in the exchange's own zone.

    Bars with no close (Yahoo appends an unfinished bar for the current session) are dropped.
    """
    result = payload["chart"]["result"][0]
    tz = ZoneInfo(result["meta"]["exchangeTimezoneName"])
    q = result["indicators"]["quote"][0]
    adj = result["indicators"].get("adjclose", [{}])[0].get("adjclose") or q["close"]
    days = [datetime.fromtimestamp(t, tz).date() for t in result["timestamp"]]
    prices = pl.DataFrame(
        {
            "ticker": [ticker] * len(days),
            "date": days,
            "open": q["open"],
            "high": q["high"],
            "low": q["low"],
            "close": q["close"],
            "adj_close": adj,
            "volume": q["volume"],
        },
        schema=PRICE_SCHEMA,
    ).drop_nulls("close")

    events = result.get("events", {})
    rows = []
    for ev in events.get("dividends", {}).values():
        rows.append(
            (ticker, datetime.fromtimestamp(ev["date"], tz).date(), "dividend", ev["amount"])
        )
    for ev in events.get("splits", {}).values():
        ratio = ev["numerator"] / ev["denominator"]
        rows.append((ticker, datetime.fromtimestamp(ev["date"], tz).date(), "split", ratio))
    actions = pl.DataFrame(rows, schema=ACTION_SCHEMA, orient="row").sort("date")
    return prices.sort("date"), actions


def load_cached(paths: Paths, ticker: str) -> tuple[pl.DataFrame, pl.DataFrame] | None:
    """Parse the cached raw file for a ticker, or None when it was never downloaded."""
    f = raw_path(paths, ticker)
    if not f.exists():
        return None
    return parse(ticker, json.loads(f.read_text(encoding="utf-8")))
