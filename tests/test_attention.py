from datetime import date, timedelta

import numpy as np
import polars as pl

from glp1 import attention as at


def synthetic(load: float, n=1400, seed=0):
    """Returns whose volatility depends on yesterday's attention with strength ``load``."""
    rng = np.random.default_rng(seed)
    days = [date(2019, 1, 1) + timedelta(days=i) for i in range(n)]
    a = np.convolve(rng.normal(size=n + 9), np.ones(10) / 10, "valid")[:n] * 3
    vol = 0.01 * np.exp(0.5 * load * np.roll(a, 1))
    r = rng.normal(0, 1, n) * vol
    ret = pl.DataFrame({"date": days, "r": r})
    att = pl.DataFrame({"date": days, "attention": a})
    return at.har_frame(ret, att)


def test_attention_helps_when_it_drives_volatility_and_not_when_it_does_not():
    for load, significant in ((1.0, True), (0.0, False)):
        d = synthetic(load)
        fb, fe, act = at.expanding_forecasts(d, ["d1", "d5", "d22"], ["att5"], date(2021, 1, 1))
        stat, p = at.dm_test(act - fb, act - fe)
        assert (p < 0.05 and stat > 0) == significant


def test_dm_test_is_symmetric_in_sign_and_flags_a_clearly_better_forecast():
    rng = np.random.default_rng(1)
    e_bad, e_good = rng.normal(0, 2, 500), rng.normal(0, 1, 500)
    s1, p1 = at.dm_test(e_bad, e_good)
    s2, _ = at.dm_test(e_good, e_bad)
    assert s1 > 0 > s2 and p1 < 0.01
