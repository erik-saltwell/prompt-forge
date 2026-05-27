"""CLI entry point for prompt-forge benchmarks."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from prompt_model.tracing import initialize_tracing

from .cj.runner import format_report as format_cj_report
from .cj.runner import run_cj_benchmark
from .ge.runner import format_report as format_ge_report
from .ge.runner import run_ge_benchmark

_DEFAULT_LOG_DIR: Path = Path.cwd() / "logs"


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
        help=(
            "Path for the JSON-lines event log. Defaults to ./logs/bench-<task>-<timestamp>.jsonl. "
            "Render via `python -m prompt_model.reporting`."
        ),
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

    ge = subparsers.add_parser("ge", help="Run the GoEmotions multi-label benchmark")
    ge.add_argument(
        "--max-concurrency",
        type=int,
        default=None,
        help="Max concurrent LLM calls during test-set evaluation (default 8).",
    )
    ge.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Number of actor/critic optimization iterations (default 16).",
    )

    args: argparse.Namespace = parser.parse_args()

    _clear_llm_call_logs()

    log_file: Path = args.log_file
    if log_file is None:
        _DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = _DEFAULT_LOG_DIR / f"bench-{args.task}-{timestamp}.jsonl"
    initialize_tracing(log_file, indent=args.log_indent)
    print(f"Event log: {log_file}", file=sys.stderr, flush=True)

    if args.task == "cj":
        cj_report = asyncio.run(run_cj_benchmark(max_concurrency=args.max_concurrency, iterations=args.iterations))
        print(format_cj_report(cj_report))
        return 0
    if args.task == "ge":
        ge_report = asyncio.run(run_ge_benchmark(max_concurrency=args.max_concurrency, iterations=args.iterations))
        print(format_ge_report(ge_report))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
