import json
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
R = json.loads((ROOT / "results" / "forecast_scores.json").read_text(encoding="utf-8"))
DOC = " ".join((ROOT / "docs" / "forecast.md").read_text(encoding="utf-8").split())
CELL = {(x["ticker"], x["h"], x["model"], x["period"]): x for x in R["cells"]}
CMP = {(x["ticker"], x["h"], x["model"]): x for x in R["comparisons"]}


def crps(tk, h, m, p):
    return CELL[(tk, h, m, p)]["crps"]


def test_primary_table_matches_results():
    for tk in ("LLY", "NVO"):
        for h in (21, 63):
            b = CMP[(tk, h, "M1")]["best_baseline"]
            row = (
                f"| {tk} | {h} | {b} | {crps(tk, h, b, 'dev'):.4f} | {crps(tk, h, 'M1', 'dev'):.4f} | "
                f"{crps(tk, h, 'M2', 'dev'):.4f} | {CMP[(tk, h, 'M1')]['dev_all_p']:.2f} | "
                f"{crps(tk, h, b, 'test'):.4f} | {crps(tk, h, 'M1', 'test'):.4f} | {crps(tk, h, 'M2', 'test'):.4f} |"
            )
            assert row in DOC, row


def test_no_model_beats_the_baseline_and_the_counts_match():
    assert len(R["comparisons"]) == 24 and "all 24 security-horizon-model comparisons" in DOC
    wins = [(x["ticker"], x["h"], x["model"]) for x in R["comparisons"] if x["beats"]]
    assert wins == [("NVO", 1, "M1")] and "one passes the decision rule" in DOC
    assert "0.01122 for B1 against 0.01115, p = 0.04" in DOC
    gain = (
        1 - CMP[("NVO", 1, "M1")]["dev_all_crps_model"] / CMP[("NVO", 1, "M1")]["dev_all_crps_base"]
    )
    assert abs(gain - 0.006) < 0.001
    n = {h: CELL[("LLY", h, "M1", "test")]["n"] for h in (1, 5, 21, 63, 126)}
    assert n[126] == 26 and ("LLY", 252, "M1", "test") not in CELL
    assert "252 development" in DOC and "26 at 126 days and none at 252" in DOC


def test_calibration_claims():
    cells = pl.DataFrame(R["cells"]).filter(pl.col("h") <= 126)
    err = (
        cells.with_columns(e80=(pl.col("c80") - 0.8).abs())
        .group_by("period", "model")
        .agg(pl.col("e80").mean())
    )
    for row in err.iter_rows(named=True):
        per = "Development" if row["period"] == "dev" else "Test"
        assert f"| {row['model']} |" in DOC
        assert f"{row['e80']:.3f}" in DOC, (per, row)
    for m, h, txt in (("B1", 21, "58%"), ("B2", 21, "58%"), ("M2", 21, "88%"), ("B1", 63, "49%")):
        assert f"{100 * CELL[('NVO', h, m, 'test')]['c80']:.0f}%" == txt
    assert f"{100 * CELL[('NVO', 63, 'M2', 'test')]['c80']:.0f}%" == "90%"
    assert round(100 * CELL[("LLY", 126, "M2", "test")]["c80"]) == 96
    assert CELL[("NVO", 126, "M2", "test")]["c80"] == 1.0
