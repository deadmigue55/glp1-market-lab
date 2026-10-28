"""The DuckDB warehouse: prices, corporate actions, factors and the security list.

Built only from the raw cache, so it can be deleted and rebuilt at any time and the network is
never touched here. Tables: ``securities``, ``prices``, ``actions``, ``factors``.
"""

from __future__ import annotations

import duckdb
import polars as pl

from glp1.config import FREEZE_DATE, Paths
from glp1.ingest import french, yahoo
from glp1.universe import UNIVERSE


def build(paths: Paths) -> dict[str, int]:
    """Rebuild the database from the raw cache and return the row count of each table."""
    paths.ensure()
    prices, actions, present = [], [], []
    for sec in UNIVERSE:
        parsed = yahoo.load_cached(paths, sec.ticker)
        if parsed is None:
            continue
        p, a = parsed
        p = p.filter(pl.col("date") <= FREEZE_DATE)
        a = a.filter(pl.col("date") <= FREEZE_DATE)
        prices.append(p)
        actions.append(a)
        present.append(sec.ticker)
    if not prices:
        raise FileNotFoundError("no cached prices; run `glp1 ingest` first")

    securities = pl.DataFrame(
        [
            (s.ticker, s.name, s.role, s.currency, s.expected_start, s.note, s.ticker in present)
            for s in UNIVERSE
        ],
        schema=["ticker", "name", "role", "currency", "expected_start", "note", "downloaded"],
        orient="row",
    )
    tables = {
        "securities": securities,
        "prices": pl.concat(prices),
        "actions": pl.concat(actions),
    }
    factors = french.load_cached(paths)
    if factors is not None:
        tables["factors"] = factors

    paths.database.unlink(missing_ok=True)
    con = duckdb.connect(str(paths.database))
    try:
        for name, df in tables.items():
            con.register("_df", df.to_arrow())
            con.execute(f"create table {name} as select * from _df")
            con.unregister("_df")
        # Analysis reads this view: it drops bars from before a security's real listing (SPAC shells).
        con.execute(
            "create view eligible_prices as select p.* from prices p join securities s using (ticker) "
            "where p.date >= cast(s.expected_start as date)"
        )
        return {n: con.sql(f"select count(*) from {n}").fetchall()[0][0] for n in tables}
    finally:
        con.close()


def connect(paths: Paths) -> duckdb.DuckDBPyConnection:
    """Open the warehouse read-only."""
    return duckdb.connect(str(paths.database), read_only=True)
