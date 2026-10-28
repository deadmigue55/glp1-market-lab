"""Data contracts for the warehouse, run by ``glp1 check``.

Each check returns findings with a severity: ``error`` breaks a downstream assumption and fails the
run, ``warn`` is a known limit that the docs must mention, ``info`` is worth knowing. The checks
exist because free feeds fail quietly (a bot-challenge page returning HTTP 200, a downsampled
series, a delisted ticker with no history), so nothing is trusted until it is checked here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import duckdb

from glp1.universe import UNIVERSE

REQUIRED_ROLES = {"maker", "benchmark", "fx"}
LATE_START_DAYS = 10
STALE_DAYS = 7
GAP_SHARE = 0.01
ADJ_TOLERANCE = 5e-4
SPY_FRENCH_MIN_CORR = 0.99
ADR_MAX_MEDIAN_LOG_GAP = 0.02


@dataclass(frozen=True)
class Finding:
    """One result of one check."""

    severity: str  # "error" | "warn" | "info"
    check: str
    detail: str


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[tuple]:
    return con.sql(sql).fetchall()


def check_integrity(con: duckdb.DuckDBPyConnection) -> list[Finding]:
    """No duplicate bars, no impossible prices."""
    out = []
    dup = _rows(
        con,
        "select ticker, date, count(*) from prices group by 1, 2 having count(*) > 1 limit 5",
    )
    if dup:
        out.append(Finding("error", "duplicates", f"duplicate (ticker, date) rows, e.g. {dup[:3]}"))
    bad = _rows(
        con,
        "select ticker, date from prices where close <= 0 or adj_close <= 0 or high < low limit 5",
    )
    if bad:
        out.append(Finding("error", "prices", f"non-positive price or high < low, e.g. {bad[:3]}"))
    if not out:
        out.append(Finding("info", "integrity", "no duplicates, no impossible prices"))
    return out


def check_coverage(con: duckdb.DuckDBPyConnection) -> list[Finding]:
    """Every security is present, starts when expected and is current."""
    out = []
    last_all = _rows(con, "select max(date) from prices")[0][0]
    have = {
        t: (a, b)
        for t, a, b in _rows(con, "select ticker, min(date), max(date) from prices group by 1")
    }
    for s in UNIVERSE:
        if s.ticker not in have:
            sev = "error" if s.role in REQUIRED_ROLES else "warn"
            out.append(Finding(sev, "coverage", f"{s.ticker} ({s.role}) has no data: {s.note}"))
            continue
        first, last = have[s.ticker]
        late = (first - date.fromisoformat(s.expected_start)).days
        if late < -LATE_START_DAYS:
            out.append(
                Finding(
                    "warn",
                    "coverage",
                    f"{s.ticker} has bars from {first}, {-late} days before {s.expected_start}: "
                    "kept in `prices`, excluded from `eligible_prices`",
                )
            )
        if late > LATE_START_DAYS:
            out.append(
                Finding(
                    "warn",
                    "coverage",
                    f"{s.ticker} starts {first}, {late} days after {s.expected_start}",
                )
            )
        if (last_all - last).days > STALE_DAYS:
            out.append(
                Finding("warn", "coverage", f"{s.ticker} stops at {last}, data runs to {last_all}")
            )
    out.append(
        Finding("info", "coverage", f"{len(have)} of {len(UNIVERSE)} series present, to {last_all}")
    )
    return out


def check_gaps(con: duckdb.DuckDBPyConnection) -> list[Finding]:
    """US-listed series should have a bar on every day SPY traded while they were listed."""
    rows = _rows(
        con,
        """
        with cal as (select date from prices where ticker = 'SPY'),
             span as (select p.ticker, min(p.date) a, max(p.date) b
                      from prices p join securities s using (ticker)
                      where s.currency = 'USD' and p.ticker <> 'SPY' group by 1)
        select span.ticker,
               count(*) filter (where cal.date between span.a and span.b) as expected,
               count(*) filter (where cal.date between span.a and span.b and q.date is null) as missing
        from span cross join cal
        left join prices q on q.ticker = span.ticker and q.date = cal.date
        group by 1
        """,
    )
    out = []
    for ticker, expected, missing in rows:
        if expected and missing / expected > GAP_SHARE:
            out.append(
                Finding("warn", "gaps", f"{ticker} misses {missing} of {expected} SPY trading days")
            )
    return out or [
        Finding("info", "gaps", "no US-listed series is missing more than 1% of trading days")
    ]


def check_adjustment(con: duckdb.DuckDBPyConnection) -> list[Finding]:
    """The adjusted/raw close ratio may only move around a dividend or split."""
    rows = _rows(
        con,
        f"""
        with r as (select ticker, date, adj_close / close as ratio,
                          lag(adj_close / close) over (partition by ticker order by date) as prev
                   from prices),
             c as (select ticker, date from r where prev is not null and abs(ratio / prev - 1) > {ADJ_TOLERANCE})
        select c.ticker, c.date from c
        left join actions a on a.ticker = c.ticker and a.date between c.date - 3 and c.date + 3
        where a.date is null order by 1, 2
        """,
    )
    if rows:
        return [
            Finding(
                "warn",
                "adjustment",
                f"adjusted close moves without a corporate action: {len(rows)} days, e.g. {rows[:3]}",
            )
        ]
    return [Finding("info", "adjustment", "adjusted close only moves around dividends and splits")]


def check_extreme_moves(con: duckdb.DuckDBPyConnection) -> list[Finding]:
    """List one-day moves above 30%; many are real news, and each is looked at in the event study."""
    rows = _rows(
        con,
        """
        with r as (select ticker, date,
                          ln(close / lag(close) over (partition by ticker order by date)) as lr
                   from prices)
        select ticker, count(*) from r
        where abs(lr) > 0.30
          and not exists (select 1 from actions a
                          where a.ticker = r.ticker and a.kind = 'split'
                            and a.date between r.date - 1 and r.date + 1)
        group by 1 order by 2 desc
        """,
    )
    if not rows:
        return [Finding("info", "extreme moves", "no one-day move above 30%")]
    return [Finding("info", "extreme moves", f"days with |move| > 30% and no split: {dict(rows)}")]


def check_spy_vs_french(con: duckdb.DuckDBPyConnection) -> list[Finding]:
    """SPY and the French market factor are independent records of the same market."""
    if not _rows(con, "select 1 from information_schema.tables where table_name = 'factors'"):
        return [Finding("warn", "spy vs french", "no factors table; run `glp1 ingest`")]
    n, corr = _rows(
        con,
        """
        with s as (select date, adj_close / lag(adj_close) over (order by date) - 1 as ret
                   from prices where ticker = 'SPY')
        select count(*), corr(s.ret, f.mkt_rf + f.rf) from s join factors f using (date) where s.ret is not null
        """,
    )[0]
    # `not corr >= x` also catches NaN, which `corr < x` lets through.
    if n == 0 or corr is None or not corr >= SPY_FRENCH_MIN_CORR:
        return [
            Finding(
                "error",
                "spy vs french",
                f"correlation {corr} over {n} days (want >= {SPY_FRENCH_MIN_CORR})",
            )
        ]
    return [Finding("info", "spy vs french", f"daily return correlation {corr:.4f} over {n} days")]


def check_adr(con: duckdb.DuckDBPyConnection) -> list[Finding]:
    """Novo's New York ADR times DKK per USD should match its Copenhagen price (1 ADR = 1 B share)."""
    gap, n = _rows(
        con,
        """
        select median(abs(ln(a.close * f.close / b.close))), count(*)
        from prices a join prices b on a.date = b.date and b.ticker = 'NOVO-B.CO'
                      join prices f on f.date = a.date and f.ticker = 'DKK=X'
        where a.ticker = 'NVO'
        """,
    )[0]
    if n == 0 or gap is None or not gap <= ADR_MAX_MEDIAN_LOG_GAP:
        return [
            Finding(
                "error",
                "adr vs local",
                f"median log gap {gap} over {n} days (want <= {ADR_MAX_MEDIAN_LOG_GAP})",
            )
        ]
    return [Finding("info", "adr vs local", f"median |log gap| {gap:.4f} over {n} days")]


def check_factors(con: duckdb.DuckDBPyConnection) -> list[Finding]:
    """Factor table is present, complete and plausible."""
    if not _rows(con, "select 1 from information_schema.tables where table_name = 'factors'"):
        return [Finding("warn", "factors", "no factors table; run `glp1 ingest`")]
    first, last, n, nulls, big = _rows(
        con,
        """
        select min(date), max(date), count(*),
               count(*) filter (where mkt_rf is null or smb is null or hml is null or rmw is null
                                 or cma is null or rf is null or mom is null),
               count(*) filter (where abs(mkt_rf) > 0.2 or abs(mom) > 0.2)
        from factors
        """,
    )[0]
    out = [Finding("info", "factors", f"{n} days, {first} to {last}")]
    last_price = _rows(con, "select max(date) from prices where ticker = 'SPY'")[0][0]
    if (last_price - last).days > STALE_DAYS:
        out.append(
            Finding(
                "warn",
                "factors",
                f"factors end {last}, {(last_price - last).days} days before prices: events after "
                "that date use the market-model fallback (methodology, amendment 1)",
            )
        )
    if nulls:
        out.append(Finding("error", "factors", f"{nulls} rows with a missing factor"))
    if big:
        out.append(Finding("error", "factors", f"{big} days with a factor move above 20%"))
    return out


def run_all(con: duckdb.DuckDBPyConnection) -> list[Finding]:
    """Run every check in a fixed order."""
    checks = [
        check_integrity,
        check_coverage,
        check_gaps,
        check_adjustment,
        check_extreme_moves,
        check_factors,
        check_spy_vs_french,
        check_adr,
    ]
    return [f for fn in checks for f in fn(con)]
