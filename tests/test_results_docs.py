import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = json.loads((ROOT / "results" / "eventstudy.json").read_text(encoding="utf-8"))
DOC = " ".join((ROOT / "docs" / "event-study.md").read_text(encoding="utf-8").split())


def cell(event_type, security, role, sample, window):
    return next(
        c
        for c in R["cells"]
        if (c["event_type"], c["security"], c["role"], c["sample"], c["window"])
        == (event_type, security, role, sample, window)
    )


def big_cells(window):
    return [c for c in R["cells"] if c["window"] == window and c["sample"] == "all" and c["n"] >= 5]


def test_sample_counts_match():
    assert f"{R['events']} ledger events give {R['pairs']} primary" in DOC
    assert f"{R['fallback_pairs']} use the market-model fallback" in DOC


def test_no_bh_rejection_and_no_small_p_in_the_three_day_window():
    assert not any(b["reject_bh10"] for b in R["bh"])
    assert f"Of {R['cells_tested_for_bh']} event type" in DOC
    cells = big_cells("m1p1")
    assert f"none of the {len(cells)} cells" in DOC
    assert all(c["p_kp"] > 0.05 and c["p_boot"] > 0.05 for c in cells)


def test_size_of_move_numbers_match():
    for event_type, sec in (
        ("earnings_guidance", "LLY"),
        ("earnings_guidance", "NVO"),
        ("trial_readout", "NVO"),
    ):
        c = cell(event_type, sec, "own", "all", "m1p1")
        assert c["p_abs"] < 0.05
        assert f"{c['mean_abs_scar']:.2f}" in DOC


def test_surprise_slopes_match_the_table():
    rows = re.findall(
        r"\| (?:[^|]+) \| (clean|all) \| (\d+) \| ([\d.]+) pp per [^|]+ \| ([\d.]+) \|", DOC
    )
    kinds = [
        "lilly_guidance_pct",
        "lilly_guidance_pct",
        "novo_guidance_pp",
        "novo_guidance_pp",
        "weight_loss_pp",
        "weight_loss_pp",
    ]
    assert len(rows) == len(kinds)
    by = {(r["kind"], r["sample"]): r for r in R["surprise_regressions"]}
    for (sample, n, slope, t), kind in zip(rows, kinds, strict=True):
        r = by[(kind, sample)]
        assert r["n"] == int(n)
        assert abs(100 * r["slope"] - float(slope)) < 0.06
        assert abs(r["t"] - float(t)) < 0.06


def test_drift_and_jump_model_claims():
    drift = big_cells("drift")
    assert len(drift) == 16
    assert sum(c["p_kp"] < 0.05 for c in drift) == 2
    assert all(c["p_boot"] > 0.05 for c in drift)
    jm = R["jump_model"]
    assert jm["divergences"] == 0
    assert f"max R-hat {jm['max_rhat']:.3f}" in DOC
    for g in jm["groups"]:
        assert (
            f"{100 * g['tau_mean']:.1f}% ({100 * g['tau_lo']:.1f}-{100 * g['tau_hi']:.1f})" in DOC
        )
