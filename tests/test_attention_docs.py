import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = json.loads((ROOT / "results" / "attention.json").read_text(encoding="utf-8"))
DOC = " ".join((ROOT / "docs" / "attention.md").read_text(encoding="utf-8").split())


def test_table_matches_results_and_the_null_claim_holds():
    for tk, res in R["volatility_test"].items():
        for name, x in res.items():
            row = (
                f"| {tk} | {name} | {x['gain_pct']:+.1f}% | {x['dm_stat']:.2f} | {x['dm_p']:.3f} |"
            ).replace("+0.0%", "+0.0%")
            assert row in DOC or row.replace("+-", "-") in DOC, row
            assert abs(x["gain_pct"]) < 2.0  # economically tiny, as the doc says
    n = {x["n"] for res in R["volatility_test"].values() for x in res.values()}
    assert n == {953} and "(953 days)" in DOC


def test_level_gain_and_null_change_claims_hold():
    v = R["volatility_test"]
    assert v["LLY"]["level"]["dm_p"] * 6 < 0.05 < v["NVO"]["level"]["dm_p"] * 6
    assert v["LLY"]["change"]["dm_p"] > 0.3 and v["NVO"]["change"]["dm_p"] > 0.3
    assert "p = 0.002" in DOC and "(p = 0.028)" in DOC
