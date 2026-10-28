"""Reverse DCF: how much GLP-1 revenue does the share price already assume?

The market value of the whole company is split into the rest of the business, valued at what
comparable large-cap pharma trade at (EV / sales), and a residual that has to be the GLP-1
franchise. That residual is turned into a peak annual sales figure by discounting a simple sales
path: a ramp from today's sales to a peak, a plateau until exclusivity ends, then a decline. Nothing
here is a forecast of sales. It is the conversion of a price into the sales it would take to
justify it, and it is always reported as a band over discount rate, margin and exclusivity
assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

import numpy as np


@dataclass(frozen=True)
class Assumptions:
    wacc: float  # annual discount rate
    fcf_margin: float  # after-tax free cash flow per dollar of GLP-1 sales
    plateau_end: float  # years from now until exclusivity ends and sales start to fall
    ramp_years: float = 6.0  # years from current sales to peak
    decline: float = 0.20  # annual sales decline after exclusivity ends
    horizon: int = 40  # years discounted explicitly


def sales_path(current: float, peak: float, a: Assumptions) -> np.ndarray:
    """Annual sales for years 1..horizon (mid-year convention is applied in ``pv``)."""
    years = np.arange(1, a.horizon + 1)
    ramp = np.minimum(years / a.ramp_years, 1.0)
    path = current + (peak - current) * ramp
    fall = np.maximum(years - a.plateau_end, 0)
    return path * (1 - a.decline) ** fall


def pv(current: float, peak: float, a: Assumptions) -> float:
    """Present value of the free cash flow of the sales path."""
    t = np.arange(1, a.horizon + 1) - 0.5
    return float(np.sum(sales_path(current, peak, a) * a.fcf_margin / (1 + a.wacc) ** t))


def implied_peak(value: float, current: float, a: Assumptions) -> float:
    """Peak sales whose present value equals ``value`` (PV is linear in the peak)."""
    base = pv(current, current, a)  # peak equal to current sales
    slope = pv(current, current + 1.0, a) - base
    return float(current + (value - base) / slope)


GRID = {
    "wacc": (0.06, 0.075, 0.09),
    "fcf_margin": (0.25, 0.34, 0.42),
    "plateau_end": (7.0, 10.0, 14.0),
}


def band(value: float, current: float) -> dict:
    """Implied peak sales over the assumption grid, in the units of ``value``."""
    peaks = [
        implied_peak(value, current, Assumptions(w, m, p))
        for w, m, p in product(GRID["wacc"], GRID["fcf_margin"], GRID["plateau_end"])
    ]
    return {
        "low": float(np.min(peaks)),
        "p10": float(np.quantile(peaks, 0.1)),
        "median": float(np.median(peaks)),
        "p90": float(np.quantile(peaks, 0.9)),
        "high": float(np.max(peaks)),
    }
