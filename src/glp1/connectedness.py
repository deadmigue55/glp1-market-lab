"""TVP-VAR connectedness (Antonakakis, Chatziantoniou and Gabauer 2020), ported from the R package.

A VAR(1) whose coefficients drift (Kalman filter with forgetting factors kappa1 for the coefficients
and kappa2 for the error covariance) and the generalised forecast-error variance decomposition of
Koop-Pesaran-Potter / Pesaran-Shin. ``tci`` is the total connectedness index in percent; ``net`` the
net directional connectedness of each series (what it transmits minus what it receives).
The filter follows ``ConnectednessApproach::TVPVAR`` with ``UninformativePrior`` and
``tests/data/tvpvar_fixture.csv`` stores that package's index for a fixed panel as the reference.
"""

from __future__ import annotations

import numpy as np


def tvp_var(x: np.ndarray, kappa1: float = 0.99, kappa2: float = 0.99):
    """Filtered VAR(1) coefficients ``b`` (T, k, k) and error covariances ``q`` (T, k, k)."""
    x = x - x.mean(axis=0)
    t, k = x.shape
    m = k * k
    q0 = np.cov(x, rowvar=False)
    beta = np.zeros(m)  # prior mean 0
    s = 4.0 * np.eye(m)  # prior variance 4
    b_t = np.zeros((t, k, k))
    q_t = np.zeros((t, k, k))
    b = np.zeros((k, k))
    for i in range(t):
        if i == 0:
            q = q0
        else:
            if i <= 1:
                gf = 0.1 * np.outer(x[i], x[i])
            else:
                e = x[i] - x[i - 1] @ b.T
                gf = np.outer(e, e)
            q = kappa2 * q_t[i - 1] + (1 - kappa2) * gf
        q_t[i] = q
        if i <= 1:
            pred, r = beta, s
        else:
            pred, r = beta, s / kappa1
        if i >= 1:
            z = np.kron(np.eye(k), x[i - 1][None, :])  # (k, m): regressors for equation rows
            rx = r @ z.T
            kv = q + z @ rx
            gain = rx @ np.linalg.pinv(kv)
            prev = beta
            beta = pred + gain @ (x[i] - z @ pred)
            s = r - gain @ (z @ r)
        b_new = beta.reshape(k, k)
        if i == 0 or np.max(np.abs(np.linalg.eigvals(b_new))) <= 1:
            b = b_new
        else:
            b = b_t[i - 1]
            beta = 0.99 * prev  # as in the R package: shrink the previous coefficients
        b_t[i] = b
    return b_t, q_t


def gfevd(b: np.ndarray, sigma: np.ndarray, horizon: int = 10) -> np.ndarray:
    """Row-normalised generalised FEVD of a VAR(1): entry (i, j) is the share of series i's
    forecast-error variance due to shocks in series j."""
    k = b.shape[0]
    num = np.zeros((k, k))
    den = np.zeros(k)
    a = np.eye(k)
    for _ in range(horizon):
        ase = a @ sigma
        num += (ase**2) / np.diag(sigma)[None, :]
        den += np.einsum("ij,ij->i", ase, a)
        a = b @ a
    theta = num / den[:, None]
    return theta / theta.sum(axis=1, keepdims=True)


def connectedness(x: np.ndarray, horizon: int = 10, kappa1: float = 0.99, kappa2: float = 0.99):
    """Time series of the total index (percent) and of net directional connectedness (percent)."""
    b_t, q_t = tvp_var(x, kappa1, kappa2)
    t, k = x.shape
    tci = np.zeros(t)
    net = np.zeros((t, k))
    for i in range(t):
        th = gfevd(b_t[i], q_t[i], horizon) * 100
        off = th - np.diag(np.diag(th))
        tci[i] = off.sum() / k
        net[i] = off.sum(axis=0) - off.sum(axis=1)  # to others minus from others
    return tci, net


BASKETS = {
    "makers": ["LLY", "NVO"],
    "challengers": ["AMGN", "VKTX", "PFE"],
    "supply": ["WST", "TMO"],
    "medtech_losers": ["DXCM", "PODD", "RMD", "INSP", "DVA", "ISRG", "ZBH"],
    "food_losers": ["MDLZ", "HSY", "PEP", "CAG"],
}
PERIODS = {  # fixed before the run: before SELECT, the re-rating, the Lilly-Novo reversal
    "to_2023-08": ("2019-01-01", "2023-08-07"),
    "2023-08_to_2024-12": ("2023-08-08", "2024-12-31"),
    "2025_on": ("2025-01-01", "2026-10-27"),
}


def run(paths) -> dict:
    """Daily market-neutral basket returns -> TCI and net directional connectedness."""
    import json

    import polars as pl

    from glp1 import warehouse

    con = warehouse.connect(paths)
    px = pl.from_arrow(con.sql("select ticker, date, adj_close from eligible_prices").arrow())
    ret = (
        px.sort("ticker", "date")
        .with_columns(r=pl.col("adj_close").pct_change().over("ticker"))
        .drop_nulls("r")
    )
    wide = ret.pivot(on="ticker", index="date", values="r").sort("date")
    cols = {
        name: pl.mean_horizontal(*[c for c in tk if c in wide.columns]).alias(name)
        for name, tk in BASKETS.items()
    }
    d = wide.select("date", "SPY", *cols.values()).drop_nulls()
    names = list(BASKETS)
    y = d.select(names).to_numpy()
    m = d["SPY"].to_numpy()
    # remove each basket's market beta so connectedness is not just the market factor
    beta = (y * m[:, None]).sum(0) / (m @ m)
    y = y - np.outer(m, beta)
    tci, net = connectedness(y)
    dates = d["date"].to_list()
    periods = {}
    for label, (a, b) in PERIODS.items():
        sel = np.array([a <= str(x) <= b for x in dates])
        periods[label] = {
            "tci_mean": float(tci[sel].mean()),
            "net": dict(zip(names, map(float, net[sel].mean(axis=0)), strict=True)),
        }
    out = {
        "baskets": BASKETS,
        "n_days": len(dates),
        "periods": periods,
        "tci_monthly": [
            {"date": str(x), "tci": float(v)}
            for x, v in zip(dates, tci, strict=True)
            if x.day <= 7 and x.weekday() == 4
        ],
    }
    d_ = paths.root / "results"
    d_.mkdir(exist_ok=True)
    (d_ / "connectedness.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    from glp1.config import get_paths

    r = run(get_paths())
    print(r["periods"])
