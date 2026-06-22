"""Command-line entry point for jcli."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__


def _load_json(source: str) -> Any:
    """Load JSON from a file path, or from stdin when source is '-'."""
    if source == "-":
        raw = sys.stdin.read()
        origin = "stdin"
    else:
        path = Path(source)
        if not path.exists():
            sys.exit(f"jcli: file not found: {source}")
        raw = path.read_text(encoding="utf-8")
        origin = path.name

    try:
        return json.loads(raw), origin
    except json.JSONDecodeError as exc:
        sys.exit(f"jcli: invalid JSON in {origin}: {exc}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="jcli",
        description="View a JSON file as a beautiful, collapsible tree in your terminal.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        default="-",
        help="Path to a .json file. Use '-' or omit to read from stdin.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"jcli {__version__}",
    )
    args = parser.parse_args(argv)

    data, origin = _load_json(args.file)

    # Import here so --version / errors don't pay the textual import cost.
    from .app import JSONTreeApp

    if not sys.stdout.isatty():
        sys.exit(
            "jcli: the interactive viewer needs a real terminal (TTY).\n"
            "Run it directly in your terminal rather than through a pipe."
        )

    JSONTreeApp(data, title=f"jcli — {origin}").run()


if __name__ == "__main__":
    main()
