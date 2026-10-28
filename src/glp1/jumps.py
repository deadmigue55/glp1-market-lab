"""Hierarchical jump-size model: how big is a day of news for each (event type, company)?

CAR_i ~ Normal(a_g, sd_i^2 + tau_g^2) for event i in group g, where sd_i is the event-study standard
deviation of the CAR (estimation noise) and tau_g is the true spread of news moves in the group.
Both a_g and log tau_g are partially pooled, because most groups hold few events. The posterior of
(a_g, tau_g) is what the forecast engine draws jump sizes from (methodology section 3.4).

``fit_pymc`` is the model; ``fit_eb`` is a closed-form empirical-Bayes check on the same data.
"""

from __future__ import annotations

import numpy as np
import polars as pl

KINDS = ("earnings_guidance", "trial_readout")


def load_events(path) -> pl.DataFrame:
    """One row per event: the issuer's own primary listing (NVO is read from NVO, not NOVO-B.CO)."""
    d = pl.read_csv(path).filter(
        pl.col("primary")
        & (pl.col("role") == "own")
        & (pl.col("security") != "NOVO-B.CO")
        & pl.col("event_type").is_in(KINDS)
        & pl.col("car_m1p1").is_not_nan()
    )
    company = pl.when(pl.col("security").is_in(["LLY", "NVO"])).then(pl.col("security"))
    return d.with_columns(
        group=pl.col("event_type") + "|" + company.otherwise(pl.lit("OTH"))
    ).select("event_id", "group", "car_m1p1", "sd_m1p1", "confounded")


def fit_eb(car: np.ndarray, sd: np.ndarray, idx: np.ndarray, n_groups: int) -> dict:
    """Method-of-moments tau per group, shrunk toward the pooled tau by group size."""
    tau2 = np.zeros(n_groups)
    for g in range(n_groups):
        m = idx == g
        tau2[g] = max(np.mean(car[m] ** 2 - sd[m] ** 2), 1e-6) if m.any() else np.nan
    pooled = max(np.mean(car**2 - sd**2), 1e-6)
    n = np.bincount(idx, minlength=n_groups)
    w = n / (n + 5)  # 5 pseudo-events of prior weight
    return {"tau": np.sqrt(w * tau2 + (1 - w) * pooled), "pooled_tau": float(np.sqrt(pooled))}


def fit_pymc(
    car: np.ndarray,
    sd: np.ndarray,
    idx: np.ndarray,
    n_groups: int,
    seed: int = 0,
    draws: int = 1000,
):
    """Partial-pooling model; returns the arviz InferenceData."""
    import pymc as pm

    with pm.Model():
        a0 = pm.Normal("a0", 0, 0.05)
        s_a = pm.HalfNormal("s_a", 0.05)
        a_z = pm.Normal("a_z", 0, 1, shape=n_groups)
        a = pm.Deterministic("a", a0 + s_a * a_z)
        m_tau = pm.Normal("m_logtau", np.log(0.04), 0.7)
        s_tau = pm.HalfNormal("s_logtau", 0.5)
        t_z = pm.Normal("t_z", 0, 1, shape=n_groups)
        tau = pm.Deterministic("tau", pm.math.exp(m_tau + s_tau * t_z))
        scale = pm.math.sqrt(sd**2 + tau[idx] ** 2)
        pm.Normal("obs", a[idx], scale, observed=car)
        return pm.sample(
            draws=draws,
            tune=1000,
            chains=4,
            cores=1,
            target_accept=0.95,
            random_seed=seed,
            progressbar=False,
        )


def summarize(path, seed: int = 0) -> dict:
    """Fit both models on the event table at ``path`` and return the numbers the docs quote."""
    import arviz as az

    d = load_events(path)
    groups = sorted(d["group"].unique().to_list())
    idx = np.array([groups.index(g) for g in d["group"]])
    car, sd = d["car_m1p1"].to_numpy(), d["sd_m1p1"].to_numpy()
    eb = fit_eb(car, sd, idx, len(groups))
    idata = fit_pymc(car, sd, idx, len(groups), seed=seed)
    post = idata.posterior
    tau, a = post["tau"].values.reshape(-1, len(groups)), post["a"].values.reshape(-1, len(groups))
    summ = az.summary(idata, var_names=["a", "tau"])
    return {
        "n_events": d.height,
        "divergences": int(idata.sample_stats["diverging"].sum()),
        "max_rhat": float(summ["r_hat"].max()),
        "min_ess_bulk": float(summ["ess_bulk"].min()),
        "groups": [
            {
                "group": g,
                "n": int((idx == i).sum()),
                "a_mean": float(a[:, i].mean()),
                "a_lo": float(np.quantile(a[:, i], 0.05)),
                "a_hi": float(np.quantile(a[:, i], 0.95)),
                "tau_mean": float(tau[:, i].mean()),
                "tau_lo": float(np.quantile(tau[:, i], 0.05)),
                "tau_hi": float(np.quantile(tau[:, i], 0.95)),
                "tau_eb": float(eb["tau"][i]),
            }
            for i, g in enumerate(groups)
        ],
    }
