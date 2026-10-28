"""S&P 500 constituents as the donor pool for synthetic difference-in-differences and GLP-1 betas.

The list is today's index membership (Wikipedia), so the pool is survivorship-biased: firms that
left the index are missing. For a donor pool this makes pre-period fits slightly too easy; the
limit is stated in docs/data.md. Prices come from the same Yahoo endpoint as the main universe.
"""

from __future__ import annotations

import re
import time
from datetime import date

import httpx
import polars as pl

from glp1.config import FREEZE_DATE, Paths
from glp1.ingest import yahoo
from glp1.universe import Security

LIST_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
# first column of the constituents table: <a class="external text" ...>TICKER</a>
_ROW = re.compile(r'<td[^>]*><a[^>]*class="external text"[^>]*>([A-Z.\-]+)</a>')


def constituents(client: httpx.Client) -> list[str]:
    """Current S&P 500 tickers in Yahoo notation (``BRK.B`` becomes ``BRK-B``)."""
    r = client.get(LIST_URL)
    r.raise_for_status()
    # the constituents table is the one whose header row starts with "Symbol"
    table = re.sub(r"<style.*?</style>", "", r.text, flags=re.S)
    table = table.split(">Symbol<", 1)[1].split("</table>", 1)[0]
    tickers = sorted({t.replace(".", "-") for t in _ROW.findall(table)})
    if not 450 <= len(tickers) <= 520:
        raise ValueError(f"expected about 500 constituents, parsed {len(tickers)}")
    return tickers


def fetch_all(paths: Paths, end: date, pause: float = 0.2) -> pl.DataFrame:
    """Download every constituent (cached files are reused) and return long adjusted closes."""
    frames = []
    with httpx.Client(headers={"User-Agent": yahoo.USER_AGENT}, timeout=30) as client:
        tickers = constituents(client)
        for t in tickers:
            if not yahoo.raw_path(paths, t).exists():
                yahoo.fetch(paths, Security(t, t, "donor"), end, client)
                time.sleep(pause)
    for t in tickers:
        got = yahoo.load_cached(paths, t)
        if got is not None:
            frames.append(got[0].select("ticker", "date", "adj_close"))
    out = pl.concat(frames).filter(pl.col("date") <= FREEZE_DATE).drop_nulls("adj_close")
    out.write_parquet(paths.processed / "donors.parquet")
    return out
