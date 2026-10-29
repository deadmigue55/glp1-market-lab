from datetime import UTC, date, datetime

import polars as pl

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
