import numpy as np

from glp1 import eventstudy as es

T = 1400
RNG = np.random.default_rng(7)
FACTORS = RNG.normal(0, 0.01, size=(T, 3))
X = np.column_stack([np.ones(T), FACTORS])
BETA = np.array([0.0002, 1.1, 0.4, -0.3])


def make_stock(rng, jump_at=None, jump=0.0, common=None, common_load=0.0):
    eps = rng.normal(0, 0.015, T)
    y = X @ BETA + eps
    if common is not None:
        y = y + common_load * common
    if jump_at is not None:
        y[jump_at] += jump
    return y


def run_cell(ys, firsts, window="m1p1"):
    cars, sds, resids = [], [], []
    for y, first in zip(ys, firsts, strict=True):
        a, b = es.window_bounds(first, first, window)
        fit = es.fit_event(y, X, first, first + 20)
        car, sd, _ = fit.car(a, b)
        cars.append(car)
        sds.append(sd)
        resids.append(fit.resid)
    return np.array(cars), np.array(sds), resids


def test_recovers_a_planted_jump_and_the_confidence_interval_covers_it():
    # 40 independent stocks, each with a +3% jump on its own day 0: CAR[-1,+1] should centre on 3%
    rng = np.random.default_rng(1)
    hits, means = 0, []
    for _ in range(60):
        firsts = [400 + 20 * i for i in range(40)]
        ys = [make_stock(rng, f, 0.03) for f in firsts]
        cars, _, _ = run_cell(ys, firsts)
        m, se = cars.mean(), cars.std(ddof=1) / np.sqrt(len(cars))
        means.append(m)
        hits += abs(m - 0.03) <= 1.96 * se
    assert abs(np.mean(means) - 0.03) < 0.002
    assert hits / 60 >= 0.88  # nominal 95%, 60 reps


def test_no_jump_gives_nominal_size_for_bmp_when_events_are_independent():
    rng = np.random.default_rng(2)
    rej = 0
    reps = 150
    for _ in range(reps):
        firsts = [400 + 20 * i for i in range(30)]
        ys = [make_stock(rng) for _ in firsts]
        cars, sds, res = run_cell(ys, firsts)
        out = es.cell_test(cars, sds, res, reps=199)
        rej += out["p_bmp"] < 0.05
    assert 0.01 <= rej / reps <= 0.10


def test_kolari_pynnonen_corrects_event_date_clustering_that_fools_the_plain_t():
    # 30 stocks share an unmodelled industry shock and all have day 0 on the same date
    rng = np.random.default_rng(3)
    plain_rej = kp_rej = 0
    reps = 150
    for _ in range(reps):
        common = rng.normal(0, 0.02, T)
        ys = [make_stock(rng, common=common, common_load=1.0) for _ in range(30)]
        cars, sds, res = run_cell(ys, [800] * 30)
        out = es.cell_test(cars, sds, res, reps=199)
        plain_rej += out["p_plain"] < 0.05
        kp_rej += out["p_kp"] < 0.05
    assert plain_rej / reps > 0.30  # badly oversized
    assert kp_rej / reps < 0.15  # much closer to 5%
    assert kp_rej < plain_rej


def test_car_standard_deviation_matches_the_simulated_spread():
    rng = np.random.default_rng(4)
    cars, sds = [], []
    for _ in range(800):
        y = make_stock(rng)
        fit = es.fit_event(y, X, 600, 620)
        c, s, n = fit.car(599, 601)
        cars.append(c)
        sds.append(s)
    assert n == 3
    assert abs(np.std(cars) / np.mean(sds) - 1) < 0.08


def test_fit_event_refuses_thin_or_missing_data():
    y = np.full(T, np.nan)
    assert es.fit_event(y, X, 600, 620) is None
    y = make_stock(np.random.default_rng(5))
    assert es.fit_event(y, X, 100, 120) is None  # estimation window starts before the data
    y2 = y.copy()
    y2[601] = np.nan
    assert es.fit_event(y2, X, 600, 620) is None  # a missing day inside the event window


def test_window_bounds_cover_both_candidate_days_for_ambiguous_events():
    assert es.window_bounds(10, 10, "m1p1") == (9, 11)
    assert es.window_bounds(10, 11, "m1p1") == (9, 12)
    assert es.window_bounds(10, 11, "d0") == (10, 11)
    assert es.window_bounds(10, 11, "drift") == (13, 31)


def test_benjamini_hochberg_known_case():
    p = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, np.nan])
    rej = es.benjamini_hochberg(p, q=0.05)
    assert rej.tolist() == [True, True, False, False, False, False, False, False, False]


def test_wild_bootstrap_detects_a_shifted_mean_and_not_a_zero_mean():
    rng = np.random.default_rng(6)
    assert es.wild_bootstrap_p(rng.normal(0.5, 1, 40), reps=2000) < 0.01
    assert es.wild_bootstrap_p(rng.normal(0, 1, 40), reps=2000) > 0.05
