from datetime import date

import polars as pl

from glp1 import fundamentals as fu
from glp1 import valuation as val


def obs(start, end, v, filed, form="10-Q"):
    return {"start": start, "end": end, "val": v, "filed": filed, "form": form}


FACTS = {
    "us-gaap": {
        "Revenues": {
            "units": {
                "USD": [
                    obs("2024-01-01", "2024-03-31", 10, "2024-05-01"),
                    obs("2024-04-01", "2024-06-30", 12, "2024-08-01"),
                    obs("2024-07-01", "2024-09-30", 14, "2024-11-01"),
                    obs("2024-01-01", "2024-09-30", 36, "2024-11-01"),
                    obs("2024-01-01", "2024-12-31", 54, "2025-02-15", "10-K"),
                    obs("2025-01-01", "2025-03-31", 20, "2025-05-01"),
                ]
            }
        }
    }
}


def test_fourth_quarter_is_the_year_minus_nine_months_and_dated_by_the_annual_filing():
    q = fu.quarterly_flow(FACTS, ["Revenues"])
    assert q["val"].to_list() == [10, 12, 14, 18, 20]
    assert q.filter(pl.col("end") == date(2024, 12, 31))["filed"][0] == date(2025, 2, 15)


def test_ttm_uses_the_latest_filing_of_the_window_and_waits_for_four_quarters():
    t = fu.ttm(fu.quarterly_flow(FACTS, ["Revenues"]))
    assert t["end"].to_list() == [date(2024, 12, 31), date(2025, 3, 31)]
    assert t["ttm"].to_list() == [54, 64]
    assert t["filed"][0] == date(2025, 2, 15)


def test_point_in_time_never_uses_a_number_before_its_filing():
    q = pl.DataFrame(
        {
            "end": [date(2024, 9, 30), date(2024, 12, 31)],
            "revenue": [100.0, 120.0],
            "filed_rev": [date(2024, 11, 1), date(2025, 2, 15)],
            "net_debt": [5.0, 7.0],
        }
    )
    # synthetic four-quarter history so a TTM exists
    hist = pl.concat(
        [
            pl.DataFrame(
                {
                    "end": [date(2024, 3, 31), date(2024, 6, 30)],
                    "revenue": [90.0, 95.0],
                    "filed_rev": [date(2024, 5, 1), date(2024, 8, 1)],
                    "net_debt": [4.0, 4.5],
                }
            ),
            q,
        ]
    )
    shares = pl.DataFrame({"filed": [date(2024, 11, 1)], "shares": [10.0]})
    days = [date(2024, 12, 31), date(2025, 2, 14), date(2025, 2, 15), date(2025, 3, 1)]
    out = val.point_in_time(hist, shares, days).sort("date")
    assert out["ttm"][0] is None  # the fourth quarter was not filed yet
    assert out["ttm"][1] is None
    assert out["ttm"][2] == 405.0 and out["ttm"][3] == 405.0
    assert out["net_debt"].to_list() == [5.0, 5.0, 7.0, 7.0]
