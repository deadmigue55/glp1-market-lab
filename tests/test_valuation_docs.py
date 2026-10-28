import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = json.loads((ROOT / "results" / "valuation.json").read_text(encoding="utf-8"))
DOC = " ".join((ROOT / "docs" / "valuation.md").read_text(encoding="utf-8").split())


def row(date):
    m = R["milestones"].get(date) or R["latest"]
    p = m["peak_c"]
    return (
        f"| {date} | ${m['ev_bn']:.0f}bn | ${m['glp1_ttm_bn']:.1f}bn | ${m['value_c_bn']:.0f}bn "
        f"| ${p['median']:.0f}bn ({p['low']:.0f}-{p['high']:.0f}) |"
    )


def test_milestone_table_matches_results():
    for date in ("2019-12-31", "2022-04-28", "2023-08-08", "2024-12-31", "2025-12-31"):
        assert row(date) in DOC
    assert row(R["latest"]["date"]) in DOC


def test_text_claims_match_results():
    latest = R["latest"]
    assert f"which is {latest['base_multiple']:.2f} today" in DOC
    assert latest["peak_lo"]["median"] < latest["peak_c"]["median"] < latest["peak_hi"]["median"]
    assert f"${latest['peak_lo']['median']:.0f}bn and ${latest['peak_hi']['median']:.0f}bn" in DOC
    assert R["milestones"]["2022-04-28"]["ev_bn"] * 4 < latest["ev_bn"]
    first = R["milestones"]["2019-12-31"]["value_c_bn"]
    assert f"(${latest['value_c_bn'] - first:.0f}bn)" in DOC
    a = R["news_day_attribution"]
    assert f"is {a['total_log_return']:.3f}" in DOC and f"{a['news_log_return']:.3f}" in DOC
    assert f"{100 * a['share_of_total']:.1f}%" in DOC
    assert f"{a['news_days']} trading days (of {a['all_days']})" in DOC
