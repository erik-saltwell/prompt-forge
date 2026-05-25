from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._render import render_report


def main(argv: list[str] | None = None) -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="python -m prompt_model.reporting",
        description="Render a self-contained HTML report from a prompt_model JSON-lines event log.",
    )
    parser.add_argument("jsonl_path", type=Path, help="Path to the JSON-lines event log written by initialize_tracing().")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Write HTML to this file instead of stdout.")
    args: argparse.Namespace = parser.parse_args(argv)

    html_text: str = render_report(args.jsonl_path)

    if args.output is None:
        sys.stdout.write(html_text)
    else:
        args.output.write_text(html_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
