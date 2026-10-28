"""Synthetic difference-in-differences (Arkhangelsky et al. 2021), ported from the R package.

``estimate`` reproduces ``synthdid::synthdid_estimate`` (Frank-Wolfe unit and time weights with the
same regularisation and sparsification). ``tests/data/sdid_fixture.csv`` holds a panel together with
the R package's answer, so the port is checked against the reference without needing R in CI.

Y is units x periods with the control units first and the treated units last; the first ``t0``
periods are pre-treatment.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _fw_step(a: np.ndarray, x: np.ndarray, b: np.ndarray, eta: float) -> np.ndarray:
    ax = a @ x
    half_grad = (ax - b) @ a + eta * x
    i = int(np.argmin(half_grad))
    dx = -x.copy()
    dx[i] = 1 - x[i]
    if not dx.any():
        return x
    d_err = a[:, i] - ax
    step = -half_grad @ dx / (d_err @ d_err + eta * dx @ dx)
    return x + min(1.0, max(0.0, step)) * dx


def _sc_weight_fw(
    y: np.ndarray, zeta: float, start: np.ndarray | None, min_decrease: float, max_iter: int
) -> np.ndarray:
    """Simplex weights over the first columns of ``y`` matching its last column (intercept on)."""
    t0 = y.shape[1] - 1
    n0 = y.shape[0]
    lam = np.full(t0, 1 / t0) if start is None else start.copy()
    y = y - y.mean(axis=0)
    a, b = y[:, :t0], y[:, t0]
    eta = n0 * zeta**2
    vals = []
    while len(vals) < max_iter and (len(vals) < 2 or vals[-2] - vals[-1] > min_decrease**2):
        lam = _fw_step(a, lam, b, eta)
        err = a @ lam - b
        vals.append(zeta**2 * (lam @ lam) + (err @ err) / n0)
    return lam


def _sparse_fw(y, zeta, min_decrease, max_iter):
    lam = _sc_weight_fw(y, zeta, None, min_decrease, 100)
    lam = np.where(lam <= lam.max() / 4, 0.0, lam)
    lam = lam / lam.sum()
    return _sc_weight_fw(y, zeta, lam, min_decrease, max_iter)


@dataclass
class Fit:
    att: float
    omega: np.ndarray  # weight on each control unit
    lam: np.ndarray  # weight on each pre-treatment period


def estimate(y: np.ndarray, n0: int, t0: int, max_iter: int = 10000) -> Fit:
    """Point estimate of the average treatment effect on the treated, with the weights."""
    n1, t1 = y.shape[0] - n0, y.shape[1] - t0
    noise = float(np.std(np.diff(y[:n0, :t0], axis=1), ddof=1))
    zeta_omega = (n1 * t1) ** 0.25 * noise
    zeta_lambda = 1e-6 * noise
    min_dec = 1e-5 * noise
    # collapse: average the treated rows and the post columns
    yc = np.empty((n0 + 1, t0 + 1))
    yc[:n0, :t0] = y[:n0, :t0]
    yc[:n0, t0] = y[:n0, t0:].mean(axis=1)
    yc[n0, :t0] = y[n0:, :t0].mean(axis=0)
    yc[n0, t0] = y[n0:, t0:].mean()
    lam = _sparse_fw(yc[:n0, :], zeta_lambda, min_dec, max_iter)
    omega = _sparse_fw(yc[:, :t0].T, zeta_omega, min_dec, max_iter)
    w_unit = np.concatenate([-omega, np.full(n1, 1 / n1)])
    w_time = np.concatenate([-lam, np.full(t1, 1 / t1)])
    return Fit(float(w_unit @ y @ w_time), omega, lam)


def placebo_se(y: np.ndarray, n0: int, t0: int, reps: int = 200, seed: int = 0) -> float:
    """Placebo standard error: treat random control subsets as treated and refit."""
    n1 = y.shape[0] - n0
    if n0 <= n1:
        raise ValueError("placebo variance needs more control units than treated units")
    rng = np.random.default_rng(seed)
    ests = []
    for _ in range(reps):
        order = rng.permutation(n0)
        placebo = np.vstack([y[order[: n0 - n1]], y[order[n0 - n1 :]]])
        ests.append(estimate(placebo, n0 - n1, t0).att)
    return float(np.sqrt((reps - 1) / reps) * np.std(ests, ddof=1))
