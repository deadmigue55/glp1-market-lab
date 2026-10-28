import io
import json
import zipfile
from datetime import date, datetime
from zoneinfo import ZoneInfo

import polars as pl

from glp1 import warehouse
from glp1.config import Paths
from glp1.ingest import french, yahoo

NY = ZoneInfo("America/New_York")


def _ts(y, m, d):
    return int(datetime(y, m, d, 9, 30, tzinfo=NY).timestamp())


def payload(closes, days, adj=None, dividends=(), splits=()):
    """A minimal Yahoo chart response."""
    adj = adj or closes
    return {
        "chart": {
            "result": [
                {
                    "meta": {"exchangeTimezoneName": "America/New_York"},
                    "timestamp": [_ts(*d) for d in days],
                    "indicators": {
                        "quote": [
                            {
                                "open": closes,
                                "high": closes,
                                "low": closes,
                                "close": closes,
                                "volume": [100] * len(closes),
                            }
                        ],
                        "adjclose": [{"adjclose": adj}],
                    },
                    "events": {
                        "dividends": {
                            str(i): {"date": _ts(*d), "amount": a}
                            for i, (d, a) in enumerate(dividends)
                        },
                        "splits": {
                            str(i): {"date": _ts(*d), "numerator": n, "denominator": m}
                            for i, (d, n, m) in enumerate(splits)
                        },
                    },
                }
            ],
            "error": None,
        }
    }


def test_parse_dates_in_exchange_zone_and_drops_unfinished_bar():
    days = [(2024, 1, 2), (2024, 1, 3), (2024, 1, 4)]
    prices, actions = yahoo.parse("X", payload([10.0, 11.0, None], days))
    assert prices["date"].to_list() == [date(2024, 1, 2), date(2024, 1, 3)]
    assert actions.is_empty()
    assert actions.schema == yahoo.ACTION_SCHEMA


def test_parse_events():
    days = [(2024, 1, 2), (2024, 1, 3)]
    _, actions = yahoo.parse(
        "X",
        payload([10.0, 11.0], days, dividends=[((2024, 1, 3), 0.5)], splits=[((2024, 1, 2), 2, 1)]),
    )
    rows = {(r["kind"], r["date"]): r["value"] for r in actions.iter_rows(named=True)}
    assert rows == {("dividend", date(2024, 1, 3)): 0.5, ("split", date(2024, 1, 2)): 2.0}


def test_raw_path_is_filesystem_safe(tmp_path):
    p = yahoo.raw_path(Paths(root=tmp_path, data=tmp_path), "DKK=X")
    assert "=" not in p.name


def french_zip(rows):
    text = (
        "This file was created by CMPT_ME\n\n,Mkt-RF,SMB\n"
        + "\n".join(rows)
        + "\n\nCopyright 2026\n"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("data.CSV", text)
    return buf.getvalue()


def test_french_parser_finds_table_and_converts_percent_to_decimal():
    df = french.parse_zip(french_zip(["20240102, 1.50, -0.25", "20240103, -2.00, 0.10"]))
    assert df.columns == ["date", "mkt_rf", "smb"]
    assert df["date"].to_list() == [date(2024, 1, 2), date(2024, 1, 3)]
    assert df["mkt_rf"].to_list() == [0.015, -0.02]


def test_warehouse_build_creates_tables_and_eligibility_view(tmp_path):
    paths = Paths(root=tmp_path, data=tmp_path).ensure()
    days = [(2024, 1, 2), (2024, 1, 3)]
    for ticker in ("SPY", "HIMS"):
        f = yahoo.raw_path(paths, ticker)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(payload([10.0, 11.0], days)), encoding="utf-8")
    counts = warehouse.build(paths)
    assert counts["prices"] == 4
    assert counts["securities"] > 20
    con = warehouse.connect(paths)
    # HIMS is only eligible from its real listing date (2021), so its 2024 bars are kept.
    assert con.sql("select count(*) from eligible_prices").fetchall()[0][0] == 4
    downloaded = pl.from_arrow(con.sql("select ticker from securities where downloaded").arrow())
    assert set(downloaded["ticker"]) == {"SPY", "HIMS"}
