"""The catalyst ledger: dated, sourced GLP-1 events, and the rule that turns a timestamp into day 0.

The ledger is a hand-curated CSV (``data/ledger/catalysts.csv``) kept in git, because it is the
project's core dataset. Every row names its source, and the surprise column is filled from that
source *before* any return is looked at (methodology, section 3). ``validate`` is run by a test and
by ``glp1 ledger`` so a malformed row cannot reach a result.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import polars as pl

from glp1.config import Paths

TAXONOMY = (
    "trial_readout",
    "regulatory",
    "pricing_policy",
    "competitor",
    "supply",
    "safety",
    "earnings_guidance",
    "mna_licensing",
)
TIMESTAMP_SOURCES = ("edgar_acceptance", "press_release", "regulator", "media")
# exact: occurred_at is when the news reached the market. upper_bound: occurred_at is only a time
# by which it had (an SEC filing after the company's own release); stated_date is the release date.
TIMINGS = ("exact", "upper_bound")
# exchange -> (time zone, regular-session close)
EXCHANGES = {
    "NYSE": ("America/New_York", time(16, 0)),
    "CPH": ("Europe/Copenhagen", time(17, 0)),
}
WINDOW = (date(2017, 1, 1), date(2026, 12, 31))

SCHEMA = {
    "event_id": pl.String,
    "ticker": pl.String,
    "also_affects": pl.String,
    "event_type": pl.String,
    "title": pl.String,
    "occurred_at": pl.Datetime("us", "UTC"),
    "timing": pl.String,
    "stated_date": pl.Date,
    "timestamp_source": pl.String,
    "source_url": pl.String,
    "scheduled": pl.Boolean,
    "announced_on": pl.Date,
    "surprise": pl.Float64,
    "surprise_basis": pl.String,
    "confounded": pl.Boolean,
    "verified_on": pl.Date,
    "notes": pl.String,
}


def path(paths: Paths):
    """Location of the ledger CSV inside the repository."""
    return paths.root / "data" / "ledger" / "catalysts.csv"


def load(paths: Paths) -> pl.DataFrame:
    """Read the ledger with its fixed schema."""
    return pl.read_csv(path(paths), schema_overrides=SCHEMA, try_parse_dates=True).select(
        list(SCHEMA)
    )


def day0(occurred_at: datetime, exchange: str, calendar: list[date]) -> date:
    """The first trading day on which the market could react to news at ``occurred_at``.

    News before the session close reaches that day's close; news after it, or on a non-trading day,
    reaches the next trading day's. ``calendar`` is the sorted list of trading dates.
    """
    zone, close = EXCHANGES[exchange]
    local = occurred_at.astimezone(ZoneInfo(zone))
    day = local.date()
    i = bisect_right(calendar, day)  # index of the first trading day after `day`
    on_trading_day = i > 0 and calendar[i - 1] == day
    if on_trading_day and local.time() < close:
        return day
    if i >= len(calendar):
        raise ValueError(f"no trading day after {day} in the calendar")
    return calendar[i]


def day0_window(
    occurred_at: datetime,
    timing: str,
    stated_date: date | None,
    exchange: str,
    calendar: list[date],
) -> tuple[date, date]:
    """First and last trading day on which the news could have first been priced.

    An ``exact`` event has one day 0. An ``upper_bound`` event is certain only when it was filed on
    its stated date before the close (the release came earlier still); otherwise the release time
    on ``stated_date`` is unknown, so day 0 is that day or the next, and the study uses [0, +1].
    """
    if timing == "exact":
        d = day0(occurred_at, exchange, calendar)
        return d, d
    if stated_date is None:
        raise ValueError("an upper_bound event needs stated_date")
    zone, close = EXCHANGES[exchange]
    local = occurred_at.astimezone(ZoneInfo(zone))
    first = calendar[bisect_left(calendar, stated_date)]  # stated_date, or the next trading day
    if local.date() == stated_date and local.time() < close:
        return first, first
    i = bisect_right(calendar, first)
    if i >= len(calendar):
        raise ValueError(f"no trading day after {first} in the calendar")
    return first, calendar[i]


def validate(df: pl.DataFrame) -> list[str]:
    """Return a list of problems; an empty list means the ledger is well formed."""
    problems: list[str] = []
    if df.columns != list(SCHEMA):
        return [f"columns differ from the schema: {df.columns}"]
    dup = df.filter(pl.col("event_id").is_duplicated())["event_id"].unique().to_list()
    if dup:
        problems.append(f"duplicate event_id: {dup}")
    for row in df.iter_rows(named=True):
        eid = row["event_id"]

        def bad(msg: str, eid=eid) -> None:
            problems.append(f"{eid}: {msg}")

        if row["event_type"] not in TAXONOMY:
            bad(f"event_type {row['event_type']!r} not in the taxonomy")
        if row["timing"] not in TIMINGS:
            bad(f"timing {row['timing']!r} not allowed")
        if row["timing"] == "upper_bound":
            if row["stated_date"] is None:
                bad("an upper_bound event needs stated_date")
            elif (
                row["occurred_at"] is not None
                and row["stated_date"] > row["occurred_at"].astimezone(UTC).date()
            ):
                bad("stated_date is after occurred_at")
        if row["timestamp_source"] not in TIMESTAMP_SOURCES:
            bad(f"timestamp_source {row['timestamp_source']!r} not allowed")
        if row["occurred_at"] is None:
            bad("missing occurred_at")
        elif not WINDOW[0] <= row["occurred_at"].date() <= WINDOW[1]:
            bad(f"occurred_at {row['occurred_at']} outside {WINDOW}")
        if not (row["source_url"] or "").startswith("https://"):
            bad("source_url must be an https URL")
        if row["surprise"] is not None and not (row["surprise_basis"] or "").strip():
            bad("a surprise value needs a surprise_basis")
        if row["scheduled"] and row["announced_on"] is None:
            bad("a scheduled event needs announced_on")
        if (
            row["scheduled"]
            and row["announced_on"] is not None
            and row["occurred_at"] is not None
            and row["announced_on"] > row["occurred_at"].astimezone(UTC).date()
        ):
            bad("announced_on is after the event")
        if row["verified_on"] is None:
            bad("not verified against its source (verified_on is empty)")
    return problems
