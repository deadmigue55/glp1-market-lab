"""Kalshi prediction-market prices for FDA decisions (public read-only API, no key).

A contract that pays $1 if CagriSema is approved before a date trades at the market's probability
of that event. It is shown next to the model's own figure; neither is hidden when they differ.
"""

from __future__ import annotations

import httpx

BASE = "https://api.elections.kalshi.com/trade-api/v2/markets"
UA = "glp1-market-lab/0.1 (https://github.com/deadmigue55/glp1-market-lab)"
EVENTS = ["KXFDAAPPROVE-CAG"]


def implied_probability(m: dict) -> float | None:
    """Midpoint of the bid and ask when both are quoted and sane, else the last trade."""
    bid, ask = float(m.get("yes_bid_dollars") or 0), float(m.get("yes_ask_dollars") or 0)
    if 0 < bid <= ask < 1 and ask - bid <= 0.15:
        return round((bid + ask) / 2, 4)
    last = m.get("last_price_dollars")
    return round(float(last), 4) if last not in (None, "") else None


def fetch(client: httpx.Client | None = None) -> list[dict]:
    """Active contracts of the tracked events with their implied probabilities."""
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": UA}, timeout=30)
    out = []
    try:
        for ev in EVENTS:
            r = client.get(BASE, params={"event_ticker": ev, "limit": 50})
            r.raise_for_status()
            for m in r.json().get("markets", []):
                if m.get("status") != "active":
                    continue
                out.append(
                    {
                        "ticker": m["ticker"],
                        "title": m["title"],
                        "closes": m["close_time"],
                        "bid": m.get("yes_bid_dollars"),
                        "ask": m.get("yes_ask_dollars"),
                        "last": m.get("last_price_dollars"),
                        "probability": implied_probability(m),
                    }
                )
    finally:
        if own:
            client.close()
    return sorted(out, key=lambda x: x["closes"])
