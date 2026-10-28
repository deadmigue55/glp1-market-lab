from pathlib import Path

import numpy as np

from glp1 import connectedness as cn

DATA = Path(__file__).parent / "data"


def test_matches_the_r_package_on_the_fixture_panel():
    x = np.loadtxt(DATA / "tvpvar_fixture.csv", delimiter=",")
    ref = np.loadtxt(DATA / "tvpvar_fixture_r.csv")
    tci, _ = cn.connectedness(x)
    assert np.abs(tci - ref).max() < 1e-6


def test_independent_series_have_low_connectedness_and_a_transmitter_is_net_positive():
    rng = np.random.default_rng(1)
    t = 600
    indep = rng.normal(size=(t, 3))
    low, _ = cn.connectedness(indep)
    # series 0 drives series 1 and 2 with a lag; nothing feeds back
    x = rng.normal(size=(t, 3))
    for i in range(1, t):
        x[i, 1] += 0.7 * x[i - 1, 0]
        x[i, 2] += 0.7 * x[i - 1, 0]
    high, net = cn.connectedness(x)
    assert high[100:].mean() > low[100:].mean() + 3
    assert net[100:, 0].mean() > 0 > net[100:, 1].mean()


def test_gfevd_rows_sum_to_one():
    th = cn.gfevd(np.array([[0.5, 0.2], [0.1, 0.3]]), np.array([[1.0, 0.3], [0.3, 2.0]]))
    assert np.allclose(th.sum(axis=1), 1)
