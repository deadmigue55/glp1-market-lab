"""SIC industry codes for the donor pool, from SEC EDGAR, to screen out GLP-1-exposed industries.

A donor must be unlikely to be repriced by GLP-1 news: pharma, medical devices, health services and
food and beverage companies are excluded (``EXCLUDED``). SIC is the registrant's own filing code, a
coarse but objective screen, and it is fixed before any synthetic-control weight is computed.
"""

from __future__ import annotations

import json

import polars as pl

from glp1.config import Paths
from glp1.ingest.edgar import SUBMISSIONS, EdgarClient

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
# SIC ranges (inclusive) of industries a GLP-1 story could plausibly touch
EXCLUDED = [
    (100, 999),  # agriculture
    (2000, 2199),  # food, beverages, tobacco
    (2830, 2836),  # drugs, biologicals
    (3841, 3851),  # surgical, medical and dental instruments
    (5140, 5149),  # wholesale groceries
    (5400, 5499),  # food stores
    (5810, 5819),  # eating places
    (5912, 5912),  # drug stores
    (8000, 8099),  # health services
    (6324, 6324),  # hospital and medical service plans
]


def excluded(sic: int | None) -> bool:
    """True when the code is missing or falls in an excluded industry."""
    return sic is None or any(lo <= sic <= hi for lo, hi in EXCLUDED)


def fetch(paths: Paths, tickers: list[str]) -> pl.DataFrame:
    """SIC code for each ticker (Yahoo notation); tickers EDGAR does not list get a null SIC."""
    client = EdgarClient(paths)
    try:
        raw = client.cached("company_tickers.json", TICKERS_URL, "company_tickers")
        cik_of = {v["ticker"].upper(): int(v["cik_str"]) for v in json.loads(raw).values()}
        rows = []
        for t in tickers:
            cik = cik_of.get(t.replace("-", ".").upper()) or cik_of.get(t.upper())
            sic, desc = None, None
            if cik:
                body = client.cached(
                    f"sic/CIK{cik:010d}.json", SUBMISSIONS.format(cik=cik, suffix=""), t
                )
                if body:
                    j = json.loads(body)
                    sic = int(j["sic"]) if j.get("sic") else None
                    desc = j.get("sicDescription")
            rows.append((t, cik, sic, desc))
    finally:
        client.close()
    out = pl.DataFrame(
        rows,
        schema={"ticker": pl.String, "cik": pl.Int64, "sic": pl.Int64, "sic_desc": pl.String},
        orient="row",
    )
    out.write_parquet(paths.processed / "donor_sic.parquet")
    return out
