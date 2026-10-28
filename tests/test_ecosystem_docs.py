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
        assert (
            f"{100 * e['att']:.1f}% ({100 * e['se']:.1f}) | {100 * e['baseline_did_vs_spy']:.1f}%"
            in DOC
        )
    assert all(e["n_donors"] == 403 for e in ECO) and "403 S&P 500 donors" in DOC
    assert est("LLY-20220428-surmount1", "all_losers", 13)["att"] < 0.02
    surmount = [e for e in ECO if e["event_id"].endswith("surmount1")]
    assert all(abs(e["att"]) < 2 * e["se"] or e["horizon_weeks"] == 52 for e in surmount)


def test_factor_numbers_match():
    assert f"{FAC['factor_days']} days" in DOC and f"{FAC['n_betas']} S&P 500 stocks" in DOC
    assert f"is {FAC['spearman_ab']:.3f} (p = {FAC['spearman_p']:.3f})" in DOC
    assert f"correlates {FAC['pca_abs_corr']:.2f}" in DOC
    assert f"quintiles is {FAC['top_quintile_b_minus_bottom_quintile_b']:.3f}" in DOC
    top = [t for t, _ in FAC["most_positive_window_b"][:4]]
    assert top == ["CRL", "IQV", "BIIB", "ABBV"]


def test_connectedness_table_matches():
    p = CON["periods"]
    for key in ("to_2023-08", "2023-08_to_2024-12", "2025_on"):
        assert f"{p[key]['tci_mean']:.1f}%" in DOC
    assert p["2025_on"]["net"]["makers"] > 0 > p["2025_on"]["net"]["medtech_losers"]
    assert f"makers ({p['2025_on']['net']['makers']:+.1f})" in DOC
