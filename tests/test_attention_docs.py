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
            assert abs(x["gain_pct"]) < 1.0 and x["dm_p"] > 0.5
    n = {x["n"] for res in R["volatility_test"].values() for x in res.values()}
    assert n == {953} and "(953 days)" in DOC
