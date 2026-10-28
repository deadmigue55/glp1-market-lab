"""SEC EDGAR filings: exact acceptance times and press-release text for company announcements.

The catalyst ledger needs a timestamp for each event that is public and checkable. For Lilly
(8-K) and Novo Nordisk (6-K) every material announcement is filed with the SEC, and EDGAR records
the second at which the filing was accepted, so that is the clock the event study uses to decide
whether news reached the market before or after the close.

SEC fair-access rules: a descriptive User-Agent (``SEC_USER_AGENT`` in ``.env``) and at most 10
requests a second. Requests here are spaced at 0.12 s. Everything is cached under
``data/raw/edgar``.
"""

from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime
from pathlib import Path

import httpx
import polars as pl

from glp1.config import Paths, sec_user_agent
from glp1.ingest import manifest

SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}{suffix}.json"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{nodash}/"
PAUSE = 0.12
FORMS = {"8-K", "6-K"}
LEAD_CHARS = 2500

FILING_SCHEMA = {
    "cik": pl.Int64,
    "accession": pl.String,
    "form": pl.String,
    "filing_date": pl.Date,
    "accepted_at": pl.Datetime("us", "UTC"),
    "items": pl.String,
    "primary_doc": pl.String,
}


class TextExtractor:
    """Collect the visible text of an HTML page (scripts and styles skipped)."""

    def __init__(self) -> None:
        from html.parser import HTMLParser

        outer = self

        class _P(HTMLParser):
            skip = 0

            def handle_starttag(self, tag, attrs):
                if tag in ("script", "style"):
                    self.skip += 1

            def handle_endtag(self, tag):
                if tag in ("script", "style") and self.skip:
                    self.skip -= 1

            def handle_data(self, data):
                if not self.skip:
                    outer.parts.append(data)

        self.parts: list[str] = []
        self._parser = _P()

    def text(self, markup: str) -> str:
        self._parser.feed(markup)
        return re.sub(r"\s+", " ", html.unescape(" ".join(self.parts))).strip()


def lead_text(markup: str, limit: int = LEAD_CHARS) -> str:
    """The first ``limit`` characters of a document's visible text."""
    return TextExtractor().text(markup)[:limit]


def parse_submissions(cik: int, payloads: list[dict]) -> pl.DataFrame:
    """Turn the ``recent`` block (and any older-file blocks) into one frame of 8-K/6-K filings."""
    rows = []
    for p in payloads:
        block = p.get("filings", {}).get("recent", p)
        if "accessionNumber" not in block:
            continue
        for i, acc in enumerate(block["accessionNumber"]):
            form = block["form"][i]
            if form not in FORMS:
                continue
            accepted = datetime.fromisoformat(block["acceptanceDateTime"][i].replace("Z", "+00:00"))
            rows.append(
                (
                    cik,
                    acc,
                    form,
                    datetime.fromisoformat(block["filingDate"][i]).date(),
                    accepted,
                    block["items"][i] if "items" in block else "",
                    block["primaryDocument"][i],
                )
            )
    df = pl.DataFrame(rows, schema=FILING_SCHEMA, orient="row")
    return df.unique(subset="accession").sort("accepted_at")


_ROW = re.compile(
    r'href="([^"]+)"[^>]*>([^<]+)</a>\s*</td>\s*<td[^>]*>\s*([A-Z0-9][A-Za-z0-9.\-]*)\s*</td>'
)


def pick_document(index_html: str, primary: str) -> str:
    """The press-release exhibit (EX-99*) if the filing has one, otherwise the primary document."""
    for href, name, doc_type in _ROW.findall(index_html):
        if doc_type.upper().startswith("EX-99"):
            return name.strip() or Path(href).name
    return primary


class EdgarClient:
    """A rate-limited, cached SEC client."""

    def __init__(self, paths: Paths) -> None:
        agent = sec_user_agent()
        if not agent:
            raise RuntimeError("set SEC_USER_AGENT in .env (SEC requires it); see .env.example")
        self.paths = paths
        self.http = httpx.Client(headers={"User-Agent": agent}, timeout=30, follow_redirects=True)
        self._last = 0.0

    def close(self) -> None:
        self.http.close()

    def get(self, url: str) -> httpx.Response:
        for attempt in range(4):
            wait = PAUSE - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            r = self.http.get(url)
            if r.status_code in (429, 503):
                time.sleep(2 * (attempt + 1))
                continue
            return r
        return r

    def cached(self, rel: str, url: str, source_key: str) -> bytes | None:
        """Fetch ``url`` into ``data/raw/edgar/<rel>`` once; return the bytes (None if absent)."""
        out = self.paths.raw / "edgar" / rel
        if out.exists():
            return out.read_bytes()
        r = self.get(url)
        if r.status_code == 404:
            manifest.record(self.paths, "edgar", source_key, url, "missing", b"", None)
            return None
        r.raise_for_status()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(r.content)
        manifest.record(self.paths, "edgar", source_key, url, "ok", r.content, out)
        return r.content


def filings(client: EdgarClient, cik: int) -> pl.DataFrame:
    """All 8-K/6-K filings of one company, from the submissions API and its older-files pages."""
    base = client.cached(
        f"submissions/{cik}.json", SUBMISSIONS.format(cik=cik, suffix=""), str(cik)
    )
    if base is None:
        raise LookupError(f"EDGAR has no submissions file for CIK {cik}")
    main = json.loads(base)
    payloads = [main]
    for f in main["filings"].get("files", []):
        name = f["name"]
        url = f"https://data.sec.gov/submissions/{name}"
        older = client.cached(f"submissions/{name}", url, f"{cik}:{name}")
        if older is None:
            raise LookupError(f"EDGAR has no {name} for CIK {cik}")
        payloads.append(json.loads(older))
    return parse_submissions(cik, payloads)


def headline(client: EdgarClient, cik: int, accession: str, primary: str) -> str:
    """The first ``LEAD_CHARS`` characters of the filing's press release (cached)."""
    txt = client.paths.raw / "edgar" / "text" / f"{accession}.txt"
    if txt.exists():
        return txt.read_text(encoding="utf-8")
    nodash = accession.replace("-", "")
    folder = ARCHIVE.format(cik=cik, nodash=nodash)
    index = client.cached(f"index/{accession}.htm", f"{folder}{accession}-index.htm", accession)
    name = pick_document(index.decode("utf-8", "ignore"), primary) if index else primary
    doc = client.cached(f"docs/{accession}_{Path(name).name}", folder + name, accession)
    text = lead_text(doc.decode("utf-8", "ignore")) if doc else ""
    txt.parent.mkdir(parents=True, exist_ok=True)
    txt.write_text(text, encoding="utf-8")
    return text
