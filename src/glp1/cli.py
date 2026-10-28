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


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the chosen command."""
    parser = argparse.ArgumentParser(prog="glp1", description=__doc__)
    parser.add_argument("--version", action="version", version=f"glp1 {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="check the environment and probe every data source")
    p.add_argument("--offline", action="store_true", help="skip the network probes")
    p.set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
