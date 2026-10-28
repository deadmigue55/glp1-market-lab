"""Daily Fama-French five factors and momentum from Kenneth French's data library.

The files are zipped CSVs with prose before and after the table, so the parser finds the table by
its rows (a first column of eight digits, ``yyyymmdd``) instead of by line numbers. Values are
published in percent and stored here as decimals.
"""

from __future__ import annotations

import io
import zipfile

import httpx
import polars as pl

from glp1.config import Paths
from glp1.ingest import manifest

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FILES = {
    "ff5": "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
    "mom": "F-F_Momentum_Factor_daily_CSV.zip",
}
USER_AGENT = "glp1-market-lab/0.1 (https://github.com/deadmigue55/glp1-market-lab)"


def fetch(paths: Paths, client: httpx.Client | None = None) -> None:
    """Download both zips into the raw cache."""
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60)
    try:
        for key, name in FILES.items():
            r = client.get(BASE + name, follow_redirects=True)
            r.raise_for_status()
            out = paths.raw / "french" / name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(r.content)
            manifest.record(paths, "french", key, str(r.url), "ok", r.content, out)
    finally:
        if own:
            client.close()


def parse_zip(data: bytes) -> pl.DataFrame:
    """Read the daily table inside one French zip into a frame of dates and decimal returns."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        text = z.read(z.namelist()[0]).decode("latin-1")
    lines = text.splitlines()
    first = next(i for i, ln in enumerate(lines) if _is_row(ln))
    header = [c.strip().lower().replace("-", "_") for c in lines[first - 1].split(",")]
    header[0] = "date"
    rows = []
    for ln in lines[first:]:
        if not _is_row(ln):
            break
        parts = [p.strip() for p in ln.split(",")]
        rows.append(parts)
    df = pl.DataFrame(rows, schema=dict.fromkeys(header, pl.String), orient="row")
    return df.select(
        pl.col("date").str.to_date("%Y%m%d"),
        *[pl.col(c).cast(pl.Float64) / 100 for c in header[1:]],
    )


def _is_row(line: str) -> bool:
    head = line.split(",")[0].strip()
    return len(head) == 8 and head.isdigit()


def load_cached(paths: Paths) -> pl.DataFrame | None:
    """Join the five factors with momentum on date (inner), or None when not downloaded."""
    files = {k: paths.raw / "french" / v for k, v in FILES.items()}
    if not all(f.exists() for f in files.values()):
        return None
    ff5 = parse_zip(files["ff5"].read_bytes())
    mom = parse_zip(files["mom"].read_bytes())
    return ff5.join(mom, on="date", how="inner").sort("date")
