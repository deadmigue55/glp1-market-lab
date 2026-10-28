import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
DOC = " ".join((ROOT / "docs" / "ecosystem.md").read_text(encoding="utf-8").split())
ECO = json.loads((RES / "ecosystem.json").read_text(encoding="utf-8"))["estimates"]
FAC = json.loads((RES / "factor.json").read_text(encoding="utf-8"))
CON = json.loads((RES / "connectedness.json").read_text(encoding="utf-8"))


def est(event, group, h):
    return next(
        e for e in ECO if (e["event_id"], e["group"], e["horizon_weeks"]) == (event, group, h)
    )


def se(e):
    return max(e["se"], e["se_in_time"])


def test_sdid_table_matches_results():
    sel = "NVO-20230808-select"
    for group, h in (
        ("all_losers", 4),
        ("all_losers", 13),
        ("all_losers", 26),
        ("all_losers", 52),
        ("medtech_health", 13),
        ("food_drink", 13),
        ("food_drink", 52),
    ):
        e = est(sel, group, h)
        row = (
            f"{100 * e['att']:.1f}% ({100 * se(e):.1f}) | {100 * e['baseline_did_vs_spy']:.1f}% "
            f"| {100 * e['end_gap']:.1f}% |"
        )
        assert row in DOC, row
    assert all(e["n_donors"] == 373 for e in ECO) and "against 373 S&P 500 donors" in DOC
    assert all(e["n_in_time"] >= 10 for e in ECO)


def test_sdid_text_claims():
    sel = "NVO-20230808-select"
    s52 = est(sel, "all_losers", 52)
    assert f"{100 * s52['att_uniform_time']:.1f}%" in DOC
    assert min(e["lambda_max"] for e in ECO) > 0.9
    surm = est("LLY-20220428-surmount1", "all_losers", 13)
    assert f"{100 * surm['att']:.1f}% (s.e. {100 * se(surm):.1f})" in DOC
    big = [
        (e["group"], e["horizon_weeks"])
        for e in ECO
        if e["event_id"].endswith("surmount1") and abs(e["att"]) >= 2 * se(e)
    ]
    assert big == [("medtech_health", 4)]
    m4 = est("LLY-20220428-surmount1", "medtech_health", 4)
    assert f"({100 * m4['att']:.1f}%, s.e. {100 * se(m4):.1f})" in DOC
    food52, food13 = est(sel, "food_drink", 52), est(sel, "food_drink", 13)
    assert f"{abs(food52['att']) / se(food52):.1f} standard errors" in DOC
    assert f"the 13-week one {abs(food13['att']) / se(food13):.1f}" in DOC
    assert est(sel, "all_losers", 26)["end_gap"] > est(sel, "all_losers", 26)["att"]


def test_factor_numbers_match():
    assert f"{FAC['factor_days']} days" in DOC and f"{FAC['n_betas']} S&P 500 stocks" in DOC
    assert f"is {FAC['spearman_ab']:.3f} (p = {FAC['spearman_p']:.3f})" in DOC
    assert f"quintiles is {FAC['top_quintile_b_minus_bottom_quintile_b']:.3f}" in DOC
    pca = FAC["pca"]
    assert f"correlate {pca['maker_loser_resid_corr']:.2f} with each other" in DOC
    first4 = pca["pc_abs_corr_first4"]
    assert pca["best_pc"] == 3
    assert f"(correlation {first4[2]:.2f}, against {first4[0]:.2f} and {first4[1]:.2f}" in DOC
    top = [t for t, _ in FAC["most_positive_window_b"][:5]]
    assert top == ["BIIB", "ABBV", "TWLO", "MRNA", "MRK"] or all(t in DOC for t in top[:2])


def test_connectedness_table_matches():
    p = CON["periods"]
    for key in ("to_2023-08", "2023-08_to_2024-12", "2025_on"):
        assert f"{p[key]['tci_mean']:.1f}%" in DOC
    assert p["2025_on"]["net"]["makers"] > 0 > p["2025_on"]["net"]["medtech_losers"]
    assert f"makers ({p['2025_on']['net']['makers']:+.1f})" in DOC
