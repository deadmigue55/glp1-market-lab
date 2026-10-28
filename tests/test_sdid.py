from pathlib import Path

import numpy as np

from glp1 import sdid

DATA = Path(__file__).parent / "data"


def test_matches_the_r_package_on_the_fixture_panel():
    y = np.loadtxt(DATA / "sdid_fixture.csv", delimiter=",")
    ref = float((DATA / "sdid_fixture_r.txt").read_text())
    assert abs(sdid.estimate(y, 40, 60).att - ref) < 1e-4


def panel(rng, effect, n0=60, n1=5, t0=80, t1=20):
    """Treated units load on a common trend that controls only partly share, so plain DID is biased."""
    t = t0 + t1
    trend = np.cumsum(rng.normal(0.05, 1, t))
    load = np.concatenate([rng.uniform(0.2, 1.8, n0), np.full(n1, 1.6)])
    y = load[:, None] * trend[None, :] + rng.normal(0, 0.4, (n0 + n1, t))
    y[n0:, t0:] += effect
    return y


def test_recovers_a_planted_effect_where_plain_did_is_biased():
    rng = np.random.default_rng(5)
    sdid_err, did_err = [], []
    for _ in range(12):
        y = panel(rng, -3.0)
        sdid_err.append(sdid.estimate(y, 60, 80).att + 3.0)
        did = (y[60:, 80:].mean() - y[60:, :80].mean()) - (y[:60, 80:].mean() - y[:60, :80].mean())
        did_err.append(did + 3.0)
    assert abs(np.mean(sdid_err)) < 0.5
    assert np.mean(np.abs(sdid_err)) < np.mean(np.abs(did_err))


def test_weights_are_on_the_simplex_and_placebo_se_is_positive():
    y = panel(np.random.default_rng(6), 0.0)
    f = sdid.estimate(y, 60, 80)
    assert abs(f.omega.sum() - 1) < 1e-9 and abs(f.lam.sum() - 1) < 1e-9
    assert (f.omega >= 0).all() and (f.lam >= 0).all()
    assert sdid.placebo_se(y, 60, 80, reps=20) > 0
