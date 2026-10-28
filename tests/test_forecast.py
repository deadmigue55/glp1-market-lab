from datetime import date

import numpy as np
import polars as pl
from scipy import stats

from glp1 import forecast as fc


def test_crps_of_a_standard_normal_forecast_at_its_median_matches_the_closed_form():
    q = stats.norm.ppf(fc.LEVELS)
    assert abs(fc.crps_from_quantiles(q, 0.0) - (np.sqrt(2) - 1) / np.sqrt(np.pi)) < 5e-3


def test_crps_prefers_the_sharper_correct_forecast():
    rng = np.random.default_rng(0)
    y = rng.normal(0, 1, 2000)
    good, wide = stats.norm.ppf(fc.LEVELS), 3 * stats.norm.ppf(fc.LEVELS)
    assert np.mean([fc.crps_from_quantiles(good, v) for v in y]) < np.mean(
        [fc.crps_from_quantiles(wide, v) for v in y]
    )


def test_adaptive_conformal_restores_coverage_when_the_model_is_overconfident():
    rng = np.random.default_rng(1)
    base = stats.norm.ppf(fc.LEVELS) * 0.5  # claims sd 0.5; the truth has sd 1.0
    ac = fc.AdaptiveConformal()
    raw_hits, ac_hits = [], []
    for _ in range(3000):
        y = rng.normal(0, 1)
        k = ac.scale()
        adj = ac.adjust(base, k)
        raw_hits.append(base[9] <= y <= base[89])
        ac_hits.append(adj[9] <= y <= adj[89])
        ac.observe(base, y, k)
    assert np.mean(raw_hits) < 0.55
    assert abs(np.mean(ac_hits[500:]) - 0.8) < 0.03


def events():
    return pl.DataFrame(
        {
            "event_type": ["earnings_guidance", "earnings_guidance", "trial_readout"],
            "last_day0": [date(2022, 2, 1), date(2022, 5, 1), date(2023, 6, 1)],
            "car_m1p1": [0.10, -0.10, 0.30],
            "sd_m1p1": [0.02, 0.02, 0.02],
        }
    )


def test_jump_inputs_use_only_events_fully_observed_before_the_origin():
    early = fc.jump_inputs(events(), date(2022, 3, 1))
    late = fc.jump_inputs(events(), date(2024, 1, 1))
    assert early.last_report == date(2022, 2, 1)
    assert late.last_report == date(2022, 5, 1)
    assert late.sched_sd != early.sched_sd
    same_day = fc.jump_inputs(events(), date(2022, 2, 2))  # the window's +1 day is not yet closed
    assert same_day.last_report is None
    assert late.unsched_rate > early.unsched_rate == 0


def test_scheduled_reports_are_projected_from_the_last_one():
    inp = fc.JumpInputs(0.05, 0.05, 1.0, date(2022, 2, 1))
    assert fc.n_scheduled(inp, date(2022, 3, 1), 21) == 0
    assert fc.n_scheduled(inp, date(2022, 3, 1), 63) == 1  # about 2022-05-03
    assert fc.n_scheduled(inp, date(2022, 3, 1), 252) == 4


def test_garch_simulation_matches_the_fitted_unconditional_scale():
    rng = np.random.default_rng(3)
    r = rng.standard_t(6, 3000) * 0.012
    true_sd = 0.012 * np.sqrt(6 / 4)  # variance of a t(6) is 6/4
    res = fc._fit(r)
    paths = fc._paths(res, "simulation", 0)
    daily = np.std(np.diff(paths[:, :60], axis=1, prepend=0))
    assert abs(daily / true_sd - 1) < 0.10


def test_dm_flags_a_better_model_and_not_an_equal_one():
    rng = np.random.default_rng(2)
    base = rng.gamma(2, 1, 300)
    _, p_better = fc.dm_one_sided(base, base * 0.7, 21)
    _, p_equal = fc.dm_one_sided(base, base + rng.normal(0, 0.01, 300), 21)
    assert p_better < 0.01 and p_equal > 0.10
