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


def cells(window, sample, role=None):
    return [
        c
        for c in R["cells"]
        if c["window"] == window
        and c["sample"] == sample
        and c["n"] >= 5
        and (role is None or c["role"] == role)
    ]


def test_sample_counts_match():
    assert f"{R['events']} ledger events give {R['pairs']} primary" in DOC
    assert f"{R['fallback_pairs']} use the market-model fallback" in DOC


def test_signed_means_are_null_in_the_three_day_window():
    assert not any(b["reject_bh10"] for b in R["bh"])
    assert f"Of {R['cells_tested_for_bh']} event type" in DOC
    allc = cells("m1p1", "all")
    assert f"none of the {len(allc)} cells" in DOC
    assert all(c["p_kp"] > 0.05 and c["p_boot"] > 0.05 for c in allc)
    read = cells("m1p1", "all", "read") + cells("m1p1", "clean", "read")
    assert min(c["p_kp"] for c in read) > 0.125  # "below 0.13"


def test_size_of_move_numbers_and_multiplicity_match():
    quoted = [
        ("earnings_guidance", "LLY", "all"),
        ("earnings_guidance", "NVO", "all"),
        ("trial_readout", "NVO", "all"),
        ("earnings_guidance", "LLY", "clean"),
        ("trial_readout", "NVO", "clean"),
        ("earnings_guidance", "NVO", "clean"),
    ]
    for event_type, sec, sample in quoted:
        c = cell(event_type, sec, "own", sample, "m1p1")
        assert f"{c['mean_abs_scar']:.2f} (p = {c['p_abs']:.3f})" in DOC or (
            f"{c['mean_abs_scar']:.2f}" in DOC
        )
    assert cell("earnings_guidance", "NVO", "own", "clean", "m1p1")["p_abs"] > 0.10
    read = cell("earnings_guidance", "LLY", "read", "all", "m1p1")
    assert f"{read['mean_abs_scar']:.2f}" in DOC and f"p = {read['p_abs']:.3f}" in DOC
    assert f"the {len(R['bh_abs'])} size tests" in DOC
    kept = [(b["event_type"], b["security"], b["role"]) for b in R["bh_abs"] if b["reject_bh10"]]
    assert sorted(kept) == [
        ("earnings_guidance", "LLY", "own"),
        ("earnings_guidance", "LLY", "read"),
        ("earnings_guidance", "NVO", "own"),
    ]
    assert "keeps three" in DOC


def test_surprise_slopes_match_the_table():
    rows = re.findall(
        r"\| (?:[^|]+) \| (clean|all) \| (\d+) \| ([\d.]+) pp per [^|]+ \| ([\d.]+) \| ([\d.]+) \|",
        DOC,
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
    for (sample, n, slope, t, p), kind in zip(rows, kinds, strict=True):
        r = by[(kind, sample)]
        assert r["n"] == int(n)
        assert abs(100 * r["slope"] - float(slope)) < 0.06
        assert abs(r["t"] - float(t)) < 0.06
        assert abs(r["p_perm"] - float(p)) < 0.0006


def test_drift_claims():
    clean = cells("drift", "clean")
    assert len(clean) == 12 and f"Of the {len(clean)} clean-sample drift cells" in DOC
    assert sum(c["p_kp"] < 0.05 for c in clean) == 2
    assert sum(c["p_boot"] < 0.05 for c in clean) == 1
    smallest = min(min(c["p_kp"], c["p_boot"]) for c in clean)
    assert f"{smallest:.3f}" in DOC and smallest > 0.10 / len(clean)
    for sample, sec, key in (
        ("all", "NVO", "p_kp"),
        ("clean", "NVO", "p_kp"),
        ("clean", "NVO", "p_boot"),
    ):
        c = cell("trial_readout", sec, "own", sample, "drift")
        assert f"{c[key]:.3f}" in DOC.replace("0.0", "0.0")  # printed to three places
    assert f"{100 * cell('trial_readout', 'NVO', 'own', 'clean', 'drift')['mean_car']:.1f}%" in DOC


def test_jump_model_claims():
    jm = R["jump_model"]
    for key in ("all", "clean", "all_student_t"):
        assert jm[key]["divergences"] == 0 and jm[key]["max_rhat"] < 1.01
    by = {k: {g["group"]: g for g in jm[k]["groups"]} for k in jm}
    assert set(by["all"]) == {
        "earnings_guidance|LLY",
        "earnings_guidance|NVO",
        "trial_readout|LLY",
        "trial_readout|NVO",
    }

    def fmt(g):
        return f"{100 * g['tau_mean']:.1f}% ({100 * g['tau_lo']:.1f}-{100 * g['tau_hi']:.1f})"

    for name in by["all"]:
        for key in jm:
            assert fmt(by[key][name]) in DOC
        assert f"| {by['all'][name]['n']} |" in DOC
