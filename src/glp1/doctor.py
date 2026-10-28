"""Environment checks behind ``glp1 doctor``.

Every engine is checked by actually *using* it (Windows Smart App Control has silently blocked
native libraries in earlier projects), and every data source is probed over the network so a
broken free feed is noticed before a pipeline depends on it. Source probes never block: a
source that is down is a warning, because each one has a fallback or is optional.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from glp1.config import Paths, sec_user_agent

MIN_FREE_GB = 5
BROWSER_UA = "glp1-market-lab/0.1 (https://github.com/deadmigue55/glp1-market-lab)"

# name -> (url, needs the SEC identification header)
SOURCES: dict[str, tuple[str, bool]] = {
    "yahoo prices": (
        "https://query1.finance.yahoo.com/v8/finance/chart/LLY?range=5d&interval=1d",
        False,
    ),
    "stooq prices": ("https://stooq.com/q/d/l/?s=lly.us&i=d", False),
    "french factors": (
        "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
        False,
    ),
    "sec edgar": ("https://data.sec.gov/submissions/CIK0000059478.json", True),
    "clinicaltrials": (
        "https://clinicaltrials.gov/api/v2/studies?query.term=semaglutide&pageSize=1",
        False,
    ),
    "openfda": ("https://api.fda.gov/drug/drugsfda.json?limit=1", False),
    "gdelt": (
        "https://api.gdeltproject.org/api/v2/doc/doc?query=semaglutide&mode=artlist&maxrecords=1&format=json",
        False,
    ),
    "wikipedia views": (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/Semaglutide/daily/20260101/20260110",
        False,
    ),
    "kalshi": ("https://api.elections.kalshi.com/trade-api/v2/markets?limit=1", False),
}


@dataclass(frozen=True)
class Check:
    """Outcome of one environment check."""

    name: str
    ok: bool
    detail: str
    required: bool = True


def check_duckdb() -> Check:
    """Import DuckDB and run a query that reads and writes Parquet."""
    try:
        import duckdb

        with tempfile.TemporaryDirectory() as tmp:
            path = (Path(tmp) / "t.parquet").as_posix()
            con = duckdb.connect()
            con.sql(f"copy (select i as id from range(1000) t(i)) to '{path}' (format parquet)")
            total = con.sql(f"select sum(id) from '{path}'").fetchall()[0][0]
            con.close()
        if total != 499500:
            return Check("duckdb", False, f"wrong result {total}")
        return Check("duckdb", True, f"{duckdb.__version__}, Parquet round trip OK")
    except Exception as err:  # a blocked native library raises many exception types
        return Check("duckdb", False, f"{type(err).__name__}: {err}")


def check_polars() -> Check:
    """Import Polars and aggregate a small frame."""
    try:
        import polars as pl

        total = pl.DataFrame({"x": [1, 2, 3]}).select(pl.col("x").sum()).item()
        return Check("polars", total == 6, f"{pl.__version__}")
    except Exception as err:  # a blocked native library raises many exception types
        return Check("polars", False, f"{type(err).__name__}: {err}")


def check_pyarrow() -> Check:
    """Import PyArrow and build a table."""
    try:
        import pyarrow as pa

        n = pa.table({"x": [1, 2, 3]}).num_rows
        return Check("pyarrow", n == 3, f"{pa.__version__}")
    except Exception as err:  # a blocked native library raises many exception types
        return Check("pyarrow", False, f"{type(err).__name__}: {err}")


def check_disk(paths: Paths, min_free_gb: float = MIN_FREE_GB) -> Check:
    """Warn when the drive holding the data has little free space."""
    target = paths.data if paths.data.exists() else paths.root
    free_gb = shutil.disk_usage(target).free / 1e9
    return Check(
        "disk space",
        free_gb >= min_free_gb,
        f"{free_gb:,.0f} GB free on the data drive (want {min_free_gb}+)",
        required=False,
    )


def check_source(name: str, url: str, needs_sec_agent: bool = False) -> Check:
    """Probe one data source: any HTTP status below 400 counts as reachable."""
    headers = {"User-Agent": BROWSER_UA}
    if needs_sec_agent:
        agent = sec_user_agent()
        if not agent:
            return Check(name, False, "set SEC_USER_AGENT in .env (see .env.example)", False)
        headers["User-Agent"] = agent
    try:
        with httpx.stream("GET", url, headers=headers, timeout=20, follow_redirects=True) as r:
            return Check(name, r.status_code < 400, f"HTTP {r.status_code}", False)
    except httpx.HTTPError as err:
        return Check(name, False, f"{type(err).__name__}: {err}", False)


def run_all(paths: Paths, sources: bool = True) -> list[Check]:
    """Run every check; ``sources=False`` skips the network probes."""
    simple: list[Callable[[], Check]] = [check_duckdb, check_polars, check_pyarrow]
    checks = [*(fn() for fn in simple), check_disk(paths)]
    if sources:
        checks += [check_source(n, url, sec) for n, (url, sec) in SOURCES.items()]
    return checks
