"""Project paths and credentials.

Everything that touches the filesystem or secrets goes through here. Set ``GLP1_DATA_DIR`` to
keep the data elsewhere. Secrets are read from environment variables, which can live in a
local ``.env`` file (see ``.env.example``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def find_project_root(start: Path | None = None) -> Path:
    """Walk up from ``start`` until a folder containing ``pyproject.toml`` is found."""
    here = (start or Path(__file__)).resolve()
    for folder in (here, *here.parents):
        if (folder / "pyproject.toml").is_file():
            return folder
    raise FileNotFoundError("Could not find the project root (no pyproject.toml above here).")


PROJECT_ROOT = find_project_root()
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Paths:
    """Standard locations for data and outputs."""

    root: Path
    data: Path

    @property
    def raw(self) -> Path:
        """Downloaded source files, exactly as published."""
        return self.data / "raw"

    @property
    def processed(self) -> Path:
        """Cleaned, analysis-ready files."""
        return self.data / "processed"

    @property
    def database(self) -> Path:
        """Local DuckDB file holding prices, factors and the catalyst ledger."""
        return self.data / "glp1.duckdb"

    def ensure(self) -> Paths:
        """Create the data folders if they don't exist yet."""
        self.raw.mkdir(parents=True, exist_ok=True)
        self.processed.mkdir(parents=True, exist_ok=True)
        return self


def get_paths() -> Paths:
    """Resolve project paths, honouring the ``GLP1_DATA_DIR`` override."""
    data_dir = os.environ.get("GLP1_DATA_DIR")
    data = Path(data_dir).expanduser().resolve() if data_dir else PROJECT_ROOT / "data"
    return Paths(root=PROJECT_ROOT, data=data)


def sec_user_agent() -> str | None:
    """The identification string SEC EDGAR requires on every request, if configured."""
    return os.environ.get("SEC_USER_AGENT") or None
