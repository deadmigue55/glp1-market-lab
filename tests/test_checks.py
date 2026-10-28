from datetime import date, timedelta

import duckdb
import polars as pl

from glp1 import checks
from glp1.ingest.yahoo import ACTION_SCHEMA, PRICE_SCHEMA


def make_db(prices, actions=None, securities=None, factors=None):
    con = duckdb.connect()
    tables = {
        "prices": pl.DataFrame(prices, schema=PRICE_SCHEMA, orient="row"),
        "actions": pl.DataFrame(actions or [], schema=ACTION_SCHEMA, orient="row"),
        "securities": pl.DataFrame(
            securities or [("SPY", "USD")], schema=["ticker", "currency"], orient="row"
        ),
    }
    if factors is not None:
        tables["factors"] = factors
    for name, df in tables.items():
        con.register("_df", df.to_arrow())
        con.execute(f"create table {name} as select * from _df")
        con.unregister("_df")
    return con


def bar(ticker, d, close, adj=None):
    return (ticker, d, close, close, close, close, adj if adj is not None else close, 1.0)


DAYS = [date(2024, 1, 1) + timedelta(days=i) for i in range(10)]


def severities(findings, check):
    return {f.severity for f in findings if f.check == check}


def test_clean_data_has_no_integrity_error():
    con = make_db([bar("SPY", d, 100.0) for d in DAYS])
    assert severities(checks.check_integrity(con), "integrity") == {"info"}


def test_duplicate_and_negative_prices_are_errors():
    rows = [bar("SPY", d, 100.0) for d in DAYS] + [
        bar("SPY", DAYS[0], 100.0),
        bar("SPY", DAYS[1], -1.0),
    ]
    con = make_db(rows)
    found = checks.check_integrity(con)
    assert {f.check for f in found if f.severity == "error"} == {"duplicates", "prices"}


def test_adjusted_close_moving_without_an_action_is_flagged():
    rows = [bar("SPY", d, 100.0, adj=100.0 if i < 5 else 99.0) for i, d in enumerate(DAYS)]
    con = make_db(rows)
    assert severities(checks.check_adjustment(con), "adjustment") == {"warn"}


def test_adjusted_close_moving_on_a_dividend_is_fine():
    rows = [bar("SPY", d, 100.0, adj=100.0 if i < 5 else 99.0) for i, d in enumerate(DAYS)]
    con = make_db(rows, actions=[("SPY", DAYS[5], "dividend", 1.0)])
    assert severities(checks.check_adjustment(con), "adjustment") == {"info"}


def test_extreme_move_is_listed_but_a_split_day_is_not():
    rows = [bar("SPY", d, 100.0 if i < 5 else 40.0) for i, d in enumerate(DAYS)]
    plain = checks.check_extreme_moves(make_db(rows))
    assert "SPY" in plain[0].detail
    split = checks.check_extreme_moves(make_db(rows, actions=[("SPY", DAYS[5], "split", 0.4)]))
    assert split[0].detail == "no one-day move above 30%"


def test_gap_in_a_us_series_is_flagged():
    spy = [bar("SPY", d, 100.0) for d in DAYS]
    lly = [bar("LLY", d, 50.0) for d in DAYS[:4]] + [bar("LLY", d, 50.0) for d in DAYS[8:]]
    con = make_db(spy + lly, securities=[("SPY", "USD"), ("LLY", "USD")])
    found = checks.check_gaps(con)
    assert found[0].severity == "warn"
    assert "LLY" in found[0].detail


def test_spy_vs_french_flags_a_mismatch():
    spy = [bar("SPY", d, 100.0 + i * (-1) ** i) for i, d in enumerate(DAYS)]
    factors = pl.DataFrame({"date": DAYS, "mkt_rf": [0.01] * 10, "rf": [0.0] * 10})
    con = make_db(spy, factors=factors)
    assert severities(checks.check_spy_vs_french(con), "spy vs french") == {"error"}


def test_spy_vs_french_passes_when_returns_match():
    closes = [100.0, 101.0, 100.0, 103.0, 104.0, 102.0, 105.0, 107.0, 106.0, 108.0]
    spy = [bar("SPY", d, c) for d, c in zip(DAYS, closes, strict=True)]
    rets = [None] + [closes[i] / closes[i - 1] - 1 for i in range(1, 10)]
    factors = pl.DataFrame({"date": DAYS, "mkt_rf": rets, "rf": [0.0] * 10})
    con = make_db(spy, factors=factors)
    assert severities(checks.check_spy_vs_french(con), "spy vs french") == {"info"}
