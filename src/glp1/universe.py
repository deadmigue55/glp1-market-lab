"""The stocks, funds and rates the study looks at, and why each one is there.

Roles: ``maker`` sells GLP-1 drugs today, ``challenger`` is developing a rival, ``supply`` sells
into the GLP-1 supply chain or channel, ``loser`` is a business people expect GLP-1s to shrink,
``benchmark`` is a market or sector fund, ``fx`` is a currency rate. ``expected_start`` is the first
date we want data for; a later first bar is reported by the data checks, not hidden.
"""

from __future__ import annotations

from dataclasses import dataclass

DATA_START = "2017-01-02"


@dataclass(frozen=True)
class Security:
    """One Yahoo Finance series and its role in the study."""

    ticker: str
    name: str
    role: str
    currency: str = "USD"
    expected_start: str = DATA_START
    note: str = ""


UNIVERSE: tuple[Security, ...] = (
    # makers and challengers
    Security("LLY", "Eli Lilly", "maker", note="tirzepatide (Mounjaro, Zepbound), orforglipron"),
    Security("NVO", "Novo Nordisk ADR", "maker", note="semaglutide (Ozempic, Wegovy), CagriSema"),
    Security(
        "NOVO-B.CO", "Novo Nordisk B (Copenhagen)", "maker", "DKK", note="cross-check for NVO"
    ),
    Security("AMGN", "Amgen", "challenger", note="MariTide"),
    Security("VKTX", "Viking Therapeutics", "challenger", note="VK2735"),
    Security(
        "ZEAL.CO", "Zealand Pharma", "challenger", "DKK", note="petrelintide, survodutide royalty"
    ),
    Security("PFE", "Pfizer", "challenger", note="acquired Metsera in 2025"),
    Security("MTSR", "Metsera", "challenger", expected_start="2025-01-31", note="likely delisted"),
    Security("RHHBY", "Roche ADR", "challenger", note="Carmot, CT-388"),
    Security("GPCR", "Structure Therapeutics", "challenger", expected_start="2023-02-01"),
    # supply chain and channel
    Security("WST", "West Pharmaceutical Services", "supply", note="injection components"),
    Security("TMO", "Thermo Fisher Scientific", "supply", note="contract manufacturing"),
    Security(
        "HIMS",
        "Hims & Hers Health",
        "supply",
        expected_start="2021-01-21",
        note="compounded GLP-1 channel; earlier bars are the SPAC shell (de-SPAC date [to verify])",
    ),
    Security("CTLT", "Catalent", "supply", note="acquired Dec 2024; Yahoo has no data"),
    # perceived losers
    Security("DXCM", "Dexcom", "loser", note="glucose monitoring"),
    Security("PODD", "Insulet", "loser", note="insulin pumps"),
    Security("RMD", "ResMed", "loser", note="sleep apnoea devices"),
    Security("INSP", "Inspire Medical", "loser", note="sleep apnoea implant"),
    Security("DVA", "DaVita", "loser", note="dialysis"),
    Security("ISRG", "Intuitive Surgical", "loser", note="bariatric surgery volume"),
    Security("ZBH", "Zimmer Biomet", "loser", note="joint replacement"),
    Security("MDLZ", "Mondelez", "loser", note="snacks"),
    Security("HSY", "Hershey", "loser", note="confectionery"),
    Security("PEP", "PepsiCo", "loser", note="snacks and drinks"),
    Security("CAG", "Conagra", "loser", note="packaged food"),
    Security(
        "WW", "WW International", "loser", expected_start="2017-01-02", note="old series lost"
    ),
    # benchmarks and rates
    Security("SPY", "SPDR S&P 500 ETF", "benchmark"),
    Security("XLV", "Health Care Select Sector SPDR", "benchmark"),
    Security("XPH", "SPDR S&P Pharmaceuticals ETF", "benchmark"),
    Security("IHE", "iShares U.S. Pharmaceuticals ETF", "benchmark"),
    Security("DKK=X", "Danish krone per US dollar", "fx", "DKK"),
)

BY_TICKER = {s.ticker: s for s in UNIVERSE}
