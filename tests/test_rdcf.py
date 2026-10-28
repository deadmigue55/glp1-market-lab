import numpy as np

from glp1 import rdcf

A = rdcf.Assumptions(wacc=0.075, fcf_margin=0.34, plateau_end=10.0)


def test_inversion_recovers_a_planted_peak():
    value = rdcf.pv(20.0, 90.0, A)
    assert abs(rdcf.implied_peak(value, 20.0, A) - 90.0) < 1e-6


def test_value_rises_with_peak_and_margin_and_falls_with_wacc():
    assert rdcf.pv(20, 100, A) > rdcf.pv(20, 80, A)
    assert rdcf.pv(20, 80, rdcf.Assumptions(0.075, 0.42, 10)) > rdcf.pv(20, 80, A)
    assert rdcf.pv(20, 80, rdcf.Assumptions(0.09, 0.34, 10)) < rdcf.pv(20, 80, A)


def test_sales_path_ramps_plateaus_and_declines():
    p = rdcf.sales_path(10.0, 70.0, A)
    assert p[0] > 10 and np.isclose(p[5], 70.0) and np.isclose(p[9], 70.0)
    assert p[10] < p[9] and p[-1] < 0.05 * 70


def test_band_is_ordered_and_a_zero_value_implies_flat_sales():
    b = rdcf.band(rdcf.pv(20, 90, A), 20.0)
    assert b["low"] <= b["p10"] <= b["median"] <= b["p90"] <= b["high"]
    assert b["low"] < 90 < b["high"]
    flat = rdcf.band(rdcf.pv(20, 20, rdcf.Assumptions(0.075, 0.34, 10)), 20.0)
    assert flat["low"] < 20 * 1.3 and flat["high"] > 15
