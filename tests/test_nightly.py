import json
from datetime import UTC, date, datetime

import numpy as np
import polars as pl
import pytest

from glp1 import kalshi, nightly


def fcast(day: str, ticker: str = "LLY") -> dict:
    q = [0.001 * i for i in range(99)]
    return {
        "ticker": ticker,
        "origin": day,
        "spot": 100.0,
        "m1": {"1": q},
        "k": {"1": 1.0},
        "m2": {"1": q},
    }


def test_ledger_chain_detects_edit(tmp_path):
    f = tmp_path / "ledger.jsonl"
    assert nightly.append_ledger(f, [fcast("2026-10-27"), fcast("2026-10-27", "NVO")], "t") == 2
    assert nightly.append_ledger(f, [fcast("2026-10-27")], "t") == 0  # same origin is not rewritten
    assert nightly.append_ledger(f, [fcast("2026-10-28")], "t") == 1
    assert nightly.verify_ledger(f)
    f.write_text(f.read_text().replace('"spot":100.0', '"spot":101.0', 1), encoding="utf-8")
    assert not nightly.verify_ledger(f)


def test_ledger_chain_detects_deleted_line(tmp_path):
    f = tmp_path / "ledger.jsonl"
    nightly.append_ledger(f, [fcast("2026-10-26"), fcast("2026-10-27"), fcast("2026-10-28")], "t")
    lines = f.read_text().splitlines()
    f.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")
    assert not nightly.verify_ledger(f)


def test_open_session_bar_dropped():
    df = pl.DataFrame({"date": [date(2026, 10, 26), date(2026, 10, 27)], "close": [1.0, 2.0]})
    during = datetime(2026, 10, 27, 17, 0, tzinfo=UTC)  # 13:00 ET
    after = datetime(2026, 10, 27, 22, 30, tzinfo=UTC)  # 18:30 ET
    assert nightly.drop_open_session(df, during).height == 1
    assert nightly.drop_open_session(df, after).height == 2


def test_earnings_outcome_shares_sum_to_one():
    rows = [("raised", 0.05), ("raised", 0.03), ("cut", -0.04), ("flat", 0.0), ("raised", 0.02)]
    cars = pl.DataFrame(
        {
            "primary": [True] * 5,
            "role": ["own"] * 5,
            "security": ["LLY"] * 5,
            "event_type": ["earnings_guidance"] * 5,
            "surprise": [1.0, 1.0, -1.0, 0.0, 1.0],
            "car_m1p1": [r[1] for r in rows],
        }
    )
    out = nightly.earnings_outcomes(cars, "LLY")
    assert [o["label"] for o in out] == ["guidance raised", "guidance unchanged", "guidance cut"]
    assert abs(sum(o["probability"] for o in out) - 1) < 1e-3
    assert out[0]["n"] == 3 and out[0]["mean"] > 0 > out[2]["mean"]


def test_aci_state_roundtrip(tmp_path):
    class P:
        root = tmp_path

    (tmp_path / "forecasts").mkdir()
    aci = nightly.load_aci(P)
    aci["LLY"][21].alpha_t, aci["LLY"][21].scores = 0.15, [0.5, 1.2]
    nightly.save_aci(P, aci)
    back = nightly.load_aci(P)
    assert back["LLY"][21].alpha_t == 0.15 and back["LLY"][21].scores == [0.5, 1.2]
    assert back["NVO"][1].scores == []


def test_kalshi_probability_uses_midpoint_then_last():
    tight = {"yes_bid_dollars": "0.64", "yes_ask_dollars": "0.70", "last_price_dollars": "0.73"}
    assert kalshi.implied_probability(tight) == 0.67
    wide = {"yes_bid_dollars": "0.10", "yes_ask_dollars": "0.90", "last_price_dollars": "0.40"}
    assert kalshi.implied_probability(wide) == 0.40
    assert kalshi.implied_probability({}) is None


def test_earnings_outcomes_are_centred_and_scaled_to_the_model_jump():
    rng = np.random.default_rng(0)
    n = 40
    sup = rng.choice([-1.0, 0.0, 1.0], n, p=[0.2, 0.3, 0.5])
    cars = pl.DataFrame(
        {
            "primary": [True] * n,
            "role": ["own"] * n,
            "security": ["LLY"] * n,
            "event_type": ["earnings_guidance"] * n,
            "surprise": sup,
            "car_m1p1": 0.05 * sup + 0.02 + rng.normal(0, 0.08, n),
        }
    )
    out = nightly.earnings_outcomes(cars, "LLY", sched_sd=0.08)
    mean = sum(o["probability"] * o["mean"] for o in out)
    var = sum(o["probability"] * (o["sd"] ** 2 + o["mean"] ** 2) for o in out)
    assert abs(mean) < 1e-3
    assert abs(var - 0.08**2) < 0.0003  # the mix has the model's own earnings-jump variance


def test_late_entry_is_not_scored_or_fed_to_the_calibrator(tmp_path):
    f = tmp_path / "ledger.jsonl"
    q = [0.001 * i - 0.05 for i in range(99)]
    body = fcast("2026-10-27") | {"horizons": [1], "m1": {"1": q}, "m2": {"1": q}, "k": {"1": 1.0}}
    nightly.append_ledger(f, [body], "2026-10-29T00:02:00+00:00")  # 20:02 ET on 10-28
    days = [date(2026, 10, 26), date(2026, 10, 27), date(2026, 10, 28)]
    px = pl.DataFrame({"date": days, "adj_close": [100.0, 101.0, 102.0]})
    aci = {"LLY": {1: nightly.fc.AdaptiveConformal()}}
    done: set[str] = set()
    card = nightly.score_ledger(f, {"LLY": px}, aci, done)
    assert card["summary"] == [] and aci["LLY"][1].scores == []
    assert done == {"LLY|2026-10-27|1"}  # remembered, so it is never reconsidered

    g = tmp_path / "ledger2.jsonl"
    nightly.append_ledger(g, [body], "2026-10-27T22:30:00+00:00")  # 18:30 ET, before the outcome
    done2: set[str] = set()
    card2 = nightly.score_ledger(g, {"LLY": px}, aci, done2)
    assert card2["summary"][0]["n"] == 1 and len(aci["LLY"][1].scores) == 1


def test_a_torn_last_line_is_ignored_but_a_torn_middle_line_is_not(tmp_path):
    f = tmp_path / "ledger.jsonl"
    nightly.append_ledger(f, [fcast("2026-10-26"), fcast("2026-10-27")], "t")
    good = f.read_text()
    f.write_text(good + '{"prev": "ab')
    assert len(nightly.read_ledger(f)) == 2
    lines = good.splitlines()
    f.write_text(lines[0][:20] + "\n" + lines[1] + "\n")
    with pytest.raises(json.JSONDecodeError):
        nightly.read_ledger(f)
