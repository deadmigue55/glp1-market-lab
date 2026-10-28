"""Command-line entry point: ``uv run glp1 <command>``."""

from __future__ import annotations

import argparse
import sys

from glp1 import __version__
from glp1.config import get_paths


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check that the environment is ready: paths, engines, disk and data sources."""
    from glp1 import doctor  # imported here so `--version` stays fast

    paths = get_paths()
    print(f"GLP-1 Market Lab v{__version__}")
    print(f"  Python      {sys.version.split()[0]}")
    print(f"  Project     {paths.root}")
    print(f"  Data        {paths.data}")

    checks = doctor.run_all(paths, sources=not args.offline)
    for c in checks:
        mark = "ok  " if c.ok else ("FAIL" if c.required else "warn")
        print(f"  {mark} {c.name:<16} {c.detail}")

    failed = [c for c in checks if c.required and not c.ok]
    print("\nAll set." if not failed else "\nSome required items need attention (see above).")
    return 1 if failed else 0


def cmd_ingest(args: argparse.Namespace) -> int:
    """Download prices and factors into the raw cache, then rebuild the warehouse."""
    from datetime import date

    import httpx

    from glp1 import warehouse
    from glp1.ingest import french, yahoo
    from glp1.universe import UNIVERSE

    paths = get_paths().ensure()
    end = date.fromisoformat(args.end) if args.end else date.today()
    with httpx.Client(headers={"User-Agent": yahoo.USER_AGENT}, timeout=30) as client:
        for sec in UNIVERSE:
            ok = yahoo.fetch(paths, sec, end, client)
            print(f"  {'ok     ' if ok else 'missing'} {sec.ticker}")
    french.fetch(paths)
    print("  ok      french factors")
    print(warehouse.build(paths))
    return 0


def cmd_edgar(args: argparse.Namespace) -> int:
    """List 8-K/6-K filings for the given companies and, unless --no-text, fetch their headlines."""
    import polars as pl

    from glp1.ingest import edgar

    paths = get_paths().ensure()
    client = edgar.EdgarClient(paths)
    frames = []
    try:
        for cik in args.cik:
            df = edgar.filings(client, cik).filter(pl.col("filing_date") >= pl.date(2017, 1, 1))
            print(f"  CIK {cik}: {df.height} filings (8-K/6-K) since 2017")
            if not args.no_text:
                leads = []
                for i, row in enumerate(df.iter_rows(named=True), 1):
                    leads.append(edgar.headline(client, cik, row["accession"], row["primary_doc"]))
                    if i % 100 == 0:
                        print(f"    {i}/{df.height}")
                df = df.with_columns(pl.Series("lead", leads))
            frames.append(df)
    finally:
        client.close()
    out = paths.processed / "edgar_filings.parquet"
    pl.concat(frames, how="diagonal").write_parquet(out)
    print(f"wrote {out}")
    return 0


def cmd_ledger(_: argparse.Namespace) -> int:
    """Validate the catalyst ledger and summarise it; exit 1 when any row is malformed."""
    from glp1 import ledger

    df = ledger.load(get_paths())
    problems = ledger.validate(df)
    for p in problems:
        print(f"  problem  {p}")
    by_type = df.group_by("event_type").len().sort("event_type")
    print(f"{df.height} events; by type: {dict(by_type.iter_rows())}")
    print(f"{len(problems)} problems" if problems else "Ledger is well formed.")
    return 1 if problems else 0


def cmd_build(_: argparse.Namespace) -> int:
    """Rebuild the warehouse from the raw cache without touching the network."""
    from glp1 import warehouse

    print(warehouse.build(get_paths()))
    return 0


def cmd_check(_: argparse.Namespace) -> int:
    """Run the data contracts on the warehouse; exit 1 when any is an error."""
    from glp1 import checks, warehouse

    con = warehouse.connect(get_paths())
    findings = checks.run_all(con)
    for f in findings:
        print(f"  {f.severity:<5} {f.check:<14} {f.detail}")
    errors = [f for f in findings if f.severity == "error"]
    print(f"\n{len(errors)} errors" if errors else "\nNo errors.")
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the chosen command."""
    parser = argparse.ArgumentParser(prog="glp1", description=__doc__)
    parser.add_argument("--version", action="version", version=f"glp1 {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="check the environment and probe every data source")
    p.add_argument("--offline", action="store_true", help="skip the network probes")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("ingest", help="download prices and factors, then build the warehouse")
    p.add_argument("--end", help="last day to request, YYYY-MM-DD (default: today)")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("edgar", help="list a company's 8-K/6-K filings and fetch their headlines")
    p.add_argument("--cik", type=int, action="append", required=True, help="SEC CIK, repeatable")
    p.add_argument("--no-text", action="store_true", help="list filings only, fetch no documents")
    p.set_defaults(func=cmd_edgar)

    p = sub.add_parser("ledger", help="validate the catalyst ledger")
    p.set_defaults(func=cmd_ledger)

    p = sub.add_parser("build", help="rebuild the warehouse from the raw cache (no network)")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("check", help="run the data contracts on the warehouse")
    p.set_defaults(func=cmd_check)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
