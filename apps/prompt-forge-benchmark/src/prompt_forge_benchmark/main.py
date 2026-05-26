"""CLI entry point for prompt-forge benchmarks."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from prompt_model.tracing import initialize_tracing

from .cj.runner import format_report, run_cj_benchmark


def _clear_llm_call_logs() -> None:
    """Remove any per-call LLM log files from `<cwd>/logs/` left over from prior runs.

    `prompt_model._llm.call._save_log` writes one `<log_name>_<timestamp>.log` per LLM
    call. Other files in the directory are left alone.
    """
    logs_dir: Path = Path.cwd() / "logs"
    if not logs_dir.is_dir():
        return
    for log_file in logs_dir.glob("*.log"):
        if log_file.is_file():
            log_file.unlink()


def main() -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(prog="prompt-forge-benchmark")
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="If provided, write a JSON-lines event log to this path. Render via `python -m prompt_model.reporting`.",
    )
    parser.add_argument(
        "--log-indent",
        type=int,
        default=None,
        help="Optional indent for the JSON log (omit for compact JSON lines).",
    )
    subparsers = parser.add_subparsers(dest="task", required=True)

    cj = subparsers.add_parser("cj", help="Run the Causal Judgement Phase 1 benchmark")
    cj.add_argument(
        "--max-concurrency",
        type=int,
        default=None,
        help="Max concurrent LLM calls during test-set evaluation (default 8).",
    )
    cj.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Number of actor/critic optimization iterations (default 16).",
    )

    args: argparse.Namespace = parser.parse_args()

    _clear_llm_call_logs()

    if args.log_file is not None:
        initialize_tracing(args.log_file, indent=args.log_indent)

    if args.task == "cj":
        report = asyncio.run(run_cj_benchmark(max_concurrency=args.max_concurrency, iterations=args.iterations))
        print(format_report(report))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
