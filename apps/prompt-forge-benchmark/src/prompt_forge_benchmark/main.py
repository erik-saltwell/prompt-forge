"""CLI entry point for prompt-forge benchmarks."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from .cj.runner import format_report, run_cj_benchmark


def _check_openai_key() -> int | None:
    """Return a non-zero exit code if OPENAI_API_KEY is missing, else None."""
    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "ERROR: OPENAI_API_KEY is not set in the environment.\n"
            "       The CJ benchmark calls OpenAI's gpt-4o for target, actor, and judge.\n"
            "       Set it with:  export OPENAI_API_KEY=sk-...",
            file=sys.stderr,
        )
        return 2
    return None


def main() -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(prog="prompt-forge-benchmark")
    subparsers = parser.add_subparsers(dest="task", required=True)

    cj = subparsers.add_parser("cj", help="Run the Causal Judgement Phase 1 benchmark")
    cj.add_argument(
        "--max-concurrency",
        type=int,
        default=8,
        help="Max concurrent LLM calls during test-set evaluation (default 8).",
    )

    args: argparse.Namespace = parser.parse_args()

    if args.task == "cj":
        rc: int | None = _check_openai_key()
        if rc is not None:
            return rc
        report = asyncio.run(run_cj_benchmark(max_concurrency=args.max_concurrency))
        print(format_report(report))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
