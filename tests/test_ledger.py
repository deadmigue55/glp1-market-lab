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
        "timing": "exact",
        "stated_date": None,
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
            row(event_id="h", timing="upper_bound"),
            row(event_id="i", timing="rumoured"),
            row(event_id="j", timing="upper_bound", stated_date=date(2024, 1, 11)),
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
        "h: an upper_bound",
        "i: timing",
        "j: stated_date is after",
    ):
        assert needle in text, needle


def window(occurred_at, stated, exchange="CPH"):
    return ledger.day0_window(occurred_at, "upper_bound", stated, exchange, CAL)


def test_upper_bound_filed_before_the_close_on_its_stated_day_is_certain():
    # filed 14:00 Copenhagen on Wed 10th: the release was earlier, so day 0 is the 10th
    assert window(utc(2024, 1, 10, 13, 0), date(2024, 1, 10)) == (date(2024, 1, 10),) * 2


def test_upper_bound_filed_after_the_close_or_later_is_a_two_day_window():
    after_close = window(utc(2024, 1, 10, 17, 0), date(2024, 1, 10))
    next_day = window(utc(2024, 1, 11, 9, 0), date(2024, 1, 10))
    assert after_close == next_day == (date(2024, 1, 10), date(2024, 1, 11))


def test_upper_bound_on_a_non_trading_stated_day_starts_at_the_next_trading_day():
    # Sat 13th released, filed Tue 16th: first trading day is the 16th; the window runs to the end
    assert ledger.day0_window(
        utc(2024, 1, 16, 9, 0), "upper_bound", date(2024, 1, 13), "CPH", [*CAL, date(2024, 1, 17)]
    ) == (date(2024, 1, 16), date(2024, 1, 17))


def test_exact_events_keep_a_single_day_0():
    d = date(2024, 1, 11)
    assert ledger.day0_window(utc(2024, 1, 10, 22, 0), "exact", None, "NYSE", CAL) == (d, d)


def test_the_committed_ledger_is_well_formed():
    from glp1.config import get_paths

    df = ledger.load(get_paths())
    assert df.height > 0
    assert ledger.validate(df) == []


def test_the_forward_calendar_is_well_formed():
    from glp1.config import get_paths

    df = ledger.load_forward(get_paths())
    assert df.height > 0
    assert ledger.validate_forward(df, date(2026, 10, 28)) == []


def test_validate_forward_flags_defects():
    bad = pl.DataFrame(
        {
            "catalyst_id": ["a", "a"],
            "ticker": ["LLY", "LLY"],
            "event_type": ["rumour", "regulatory"],
            "title": ["x", "y"],
            "window_start": [date(2027, 2, 1), date(2027, 1, 1)],
            "window_end": [date(2027, 1, 1), date(2027, 3, 1)],
            "announced_on": [None, date(2026, 12, 1)],
            "source_url": ["http://x", "https://x"],
            "notes": ["", ""],
        }
    )
    text = "\n".join(ledger.validate_forward(bad, date(2026, 10, 28)))
    for needle in ("event_type", "https", "window_start", "future", "duplicate"):
        assert needle in text, needle
