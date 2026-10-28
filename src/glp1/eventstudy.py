"""Event study: abnormal returns from a factor model and the tests that go with them.

The protocol is in ``docs/methodology.md`` section 3. The numeric core works on plain arrays so the
planted-truth tests can feed it simulated returns:

* ``fit_event`` regresses one security's returns on a factor matrix over the estimation window and
  returns the abnormal returns, residual scale and the variance of any cumulative window.
* ``cell_test`` takes the events of one cell and returns the plain cross-sectional t-test next to
  Boehmer-Musumeci-Poulsen, Kolari-Pynnönen and a wild-bootstrap p-value.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

EST_START, EST_END = -250, -30  # trading days relative to day 0
MIN_EST_OBS = 120
# window name -> (start offset, end offset); start uses the first candidate day 0 when the offset is
# <= 0 and the last one otherwise, end always uses the last (amendment 2)
WINDOWS = {"d0": (0, 0), "m1p1": (-1, 1), "p0p5": (0, 5), "p0p20": (0, 20), "drift": (2, 20)}
PRIMARY = "m1p1"


@dataclass
class EventFit:
    """The fitted model and abnormal returns of one (event, security) pair."""

    ar: np.ndarray  # abnormal return for each position in ``positions``
    positions: np.ndarray  # indices into the security's own date array
    sigma: float  # residual standard deviation over the estimation window
    n_est: int
    resid: np.ndarray  # estimation residuals in event time, length EST_END - EST_START + 1
    _xtx_inv: np.ndarray
    _x_event: np.ndarray

    def car(self, lo: int, hi: int) -> tuple[float, float, int]:
        """Cumulative abnormal return, standard deviation and day count over positions lo..hi."""
        sel = (self.positions >= lo) & (self.positions <= hi)
        n = int(sel.sum())
        if n == 0:
            return float("nan"), float("nan"), 0
        x = self._x_event[sel]
        s = x.sum(axis=0)
        var = self.sigma**2 * (n + s @ self._xtx_inv @ s)
        return float(self.ar[sel].sum()), float(np.sqrt(var)), n


def fit_event(
    y: np.ndarray, x: np.ndarray, first: int, event_hi: int, lo_offset: int = -1
) -> EventFit | None:
    """Fit the model for one event.

    ``y`` is the security's (excess) return and ``x`` the regressor matrix with a constant column,
    both indexed by the security's trading days. ``first`` is the position of the first candidate
    day 0 and ``event_hi`` the last position needed. Returns None when the estimation window has too
    few clean observations or the event window has missing data.
    """
    est = np.arange(first + EST_START, first + EST_END + 1)
    if est[0] < 0 or event_hi >= len(y):
        return None
    ye, xe = y[est], x[est]
    ok = np.isfinite(ye) & np.isfinite(xe).all(axis=1)
    if ok.sum() < MIN_EST_OBS:
        return None
    beta, *_ = np.linalg.lstsq(xe[ok], ye[ok], rcond=None)
    resid_ok = ye[ok] - xe[ok] @ beta
    k = x.shape[1]
    sigma = float(np.sqrt(resid_ok @ resid_ok / (ok.sum() - k)))
    resid = np.full(len(est), np.nan)
    resid[ok] = resid_ok
    xtx_inv = np.linalg.inv(xe[ok].T @ xe[ok])

    pos = np.arange(first + lo_offset, event_hi + 1)
    if pos[0] < 0:
        return None
    yp, xp = y[pos], x[pos]
    good = np.isfinite(yp) & np.isfinite(xp).all(axis=1)
    if not good.all():
        return None
    ar = yp - xp @ beta
    return EventFit(ar, pos, sigma, int(ok.sum()), resid, xtx_inv, xp)


def window_bounds(first: int, last: int, name: str) -> tuple[int, int]:
    """First and last position of a named window for an event whose day 0 is in first..last."""
    a, b = WINDOWS[name]
    return (first if a <= 0 else last) + a, last + b


# ── cross-sectional tests ─────────────────────────────────────────────────────


def mean_correlation(resids: list[np.ndarray], min_overlap: int = 60) -> float:
    """Average pairwise correlation of estimation residuals aligned in event time."""
    r = []
    for i in range(len(resids)):
        for j in range(i + 1, len(resids)):
            ok = np.isfinite(resids[i]) & np.isfinite(resids[j])
            if ok.sum() >= min_overlap:
                a, b = resids[i][ok], resids[j][ok]
                if a.std() > 0 and b.std() > 0:
                    r.append(float(np.corrcoef(a, b)[0, 1]))
    return float(np.mean(r)) if r else 0.0


def wild_bootstrap_p(x: np.ndarray, reps: int = 9999, seed: int = 0) -> float:
    """Two-sided p-value for mean(x) = 0: Rademacher weights on the centred sample, studentised."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 3 or x.std(ddof=1) == 0:
        return float("nan")
    t_obs = x.mean() / (x.std(ddof=1) / np.sqrt(n))
    rng = np.random.default_rng(seed)
    centred = x - x.mean()
    w = rng.choice([-1.0, 1.0], size=(reps, n))
    xb = w * centred
    sd = xb.std(axis=1, ddof=1)
    sd[sd == 0] = np.nan
    t_b = xb.mean(axis=1) / (sd / np.sqrt(n))
    return float((1 + np.sum(np.abs(t_b) >= abs(t_obs))) / (reps + 1))


def cell_test(
    cars: np.ndarray, sds: np.ndarray, resids: list[np.ndarray], reps: int = 9999, seed: int = 0
) -> dict:
    """Tests of mean CAR = 0 for one cell of events.

    ``cars`` are the cumulative abnormal returns, ``sds`` their model standard deviations and
    ``resids`` the estimation residuals (for the Kolari-Pynnönen correction).
    """
    cars, sds = np.asarray(cars, float), np.asarray(sds, float)
    n = len(cars)
    out = {"n": n, "mean_car": float(cars.mean()) if n else float("nan")}
    if n < 3:
        return out | {
            k: float("nan")
            for k in ("t_plain", "p_plain", "t_bmp", "p_bmp", "rbar", "t_kp", "p_kp", "p_boot")
        }
    t_plain = cars.mean() / (cars.std(ddof=1) / np.sqrt(n))
    scar = cars / sds
    t_bmp = scar.mean() / (scar.std(ddof=1) / np.sqrt(n))
    rbar = mean_correlation(resids)
    # Kolari-Pynnönen: shrink the BMP statistic by the cross-correlation of the residuals
    shrink = np.sqrt(max(1 - rbar, 1e-9) / (1 + (n - 1) * max(rbar, 0.0)))
    t_kp = t_bmp * shrink
    df = n - 1
    return out | {
        "t_plain": float(t_plain),
        "p_plain": float(2 * stats.t.sf(abs(t_plain), df)),
        "t_bmp": float(t_bmp),
        "p_bmp": float(2 * stats.t.sf(abs(t_bmp), df)),
        "rbar": rbar,
        "t_kp": float(t_kp),
        "p_kp": float(2 * stats.t.sf(abs(t_kp), df)),
        "p_boot": wild_bootstrap_p(cars, reps, seed),
    }


def benjamini_hochberg(p: np.ndarray, q: float = 0.10) -> np.ndarray:
    """Boolean array: which hypotheses are rejected at false-discovery rate ``q``."""
    p = np.asarray(p, float)
    ok = np.isfinite(p)
    reject = np.zeros(len(p), bool)
    idx = np.where(ok)[0]
    order = idx[np.argsort(p[idx])]
    m = len(order)
    thresh = q * (np.arange(1, m + 1) / m)
    passed = np.where(p[order] <= thresh)[0]
    if len(passed):
        reject[order[: passed.max() + 1]] = True
    return reject
