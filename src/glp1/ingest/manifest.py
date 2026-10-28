"""Download log: one row per fetch with source, URL, time, size and checksum."""

from __future__ import annotations

import csv
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from glp1.config import Paths

COLUMNS = ["fetched_at", "source", "key", "url", "status", "bytes", "sha256", "file"]


def sha256(data: bytes) -> str:
    """Hex checksum of a payload."""
    return hashlib.sha256(data).hexdigest()


def record(
    paths: Paths, source: str, key: str, url: str, status: str, data: bytes, file: Path | None
) -> None:
    """Append one fetch to ``data/raw/MANIFEST.csv`` (created with a header on first use)."""
    manifest = paths.raw / "MANIFEST.csv"
    new = not manifest.exists()
    with manifest.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(COLUMNS)
        w.writerow(
            [
                datetime.now(UTC).isoformat(timespec="seconds"),
                source,
                key,
                url,
                status,
                len(data),
                sha256(data) if data else "",
                file.relative_to(paths.data).as_posix() if file else "",
            ]
        )
