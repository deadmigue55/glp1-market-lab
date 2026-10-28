from datetime import UTC, date, datetime

import polars as pl

from glp1 import ledger

# Mon 2024-01-08 .. Fri 2024-01-12, then Mon 2024-01-15 (a US holiday, so absent), Tue 2024-01-16
CAL = [date(2024, 1, d) for d in (8, 9, 10, 11, 12, 16)]


def utc(*args):
    return datetime(*args, tzinfo=UTC)


def test_news_before_the_us_close_is_same_day():
    # 14:00 New York time on Wed 2024-01-10 = 19:00 UTC
    assert ledger.day0(utc(2024, 1, 10, 19, 0), "NYSE", CAL) == date(2024, 1, 10)


def test_news_after_the_us_close_is_next_trading_day():
    # 17:30 New York time on Fri 2024-01-12 = 22:30 UTC -> Monday is a holiday, so Tuesday 16th
    assert ledger.day0(utc(2024, 1, 12, 22, 30), "NYSE", CAL) == date(2024, 1, 16)


def test_exactly_at_the_close_counts_as_after():
    assert ledger.day0(utc(2024, 1, 10, 21, 0), "NYSE", CAL) == date(2024, 1, 11)


def test_weekend_and_holiday_news_goes_to_the_next_trading_day():
    assert ledger.day0(utc(2024, 1, 13, 15, 0), "NYSE", CAL) == date(2024, 1, 16)  # Saturday
    assert ledger.day0(utc(2024, 1, 15, 15, 0), "NYSE", CAL) == date(2024, 1, 16)  # holiday


def test_copenhagen_uses_its_own_close():
    # 16:30 Copenhagen (UTC+1 in January) = 15:30 UTC: before the 17:00 close, same day
    assert ledger.day0(utc(2024, 1, 10, 15, 30), "CPH", CAL) == date(2024, 1, 10)
    # 17:30 Copenhagen = 16:30 UTC: after the close
    assert ledger.day0(utc(2024, 1, 10, 16, 30), "CPH", CAL) == date(2024, 1, 11)


def row(**kw):
    base = {
        "event_id": "e1",
        "ticker": "LLY",
        "also_affects": "",
        "event_type": "trial_readout",
        "title": "x",
        "occurred_at": utc(2024, 1, 10, 12, 0),
        "timestamp_source": "press_release",
        "source_url": "https://example.com/a",
        "scheduled": False,
        "announced_on": None,
        "surprise": None,
        "surprise_basis": "",
        "confounded": False,
        "verified_on": date(2026, 10, 28),
        "notes": "",
    }
    base.update(kw)
    return base


def make(*rows):
    return pl.DataFrame(list(rows), schema=ledger.SCHEMA)


def test_a_clean_row_validates():
    assert ledger.validate(make(row())) == []


def test_validate_flags_each_kind_of_defect():
    problems = ledger.validate(
        make(
            row(event_id="a", event_type="rumour"),
            row(event_id="b", source_url="http://x"),
            row(event_id="c", surprise=1.0),
            row(event_id="d", scheduled=True),
            row(event_id="e", verified_on=None),
            row(event_id="f", occurred_at=utc(2010, 1, 1)),
            row(event_id="g", scheduled=True, announced_on=date(2025, 1, 1)),
            row(event_id="g"),
        )
    )
    text = "\n".join(problems)
    for needle in (
        "a: event_type",
        "b: source_url",
        "c: a surprise value",
        "d: a scheduled event",
        "e: not verified",
        "f: occurred_at",
        "g: announced_on is after",
        "duplicate event_id",
    ):
        assert needle in text, needle
