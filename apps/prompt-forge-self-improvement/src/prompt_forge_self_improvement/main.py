"""CLI entry point for prompt-forge-self-improvement."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import structlog
import structlog.dev
from structlog.typing import EventDict, WrappedLogger

from ._registry import REGISTRY
from ._runner import run_target


class _JsonlTee:
    """Structlog processor that writes JSONL to a file and passes the event dict through.

    Placed before the ConsoleRenderer so both sinks see the same structured event.
    The resulting JSONL is compatible with `python -m prompt_model.reporting`.
    """

    def __init__(self, path: Path) -> None:
        self._f = path.open("a", encoding="utf-8")

    def __call__(self, _logger: WrappedLogger, _method: str, event_dict: EventDict) -> EventDict:
        try:
            self._f.write(json.dumps(dict(event_dict), default=str) + "\n")
            self._f.flush()
        except Exception:  # noqa: BLE001
            pass
        return event_dict


def _configure_logging(trace_path: Path) -> None:
    """Configure structlog with dual output: JSONL trace file + human-readable stderr.

    The trace file is compatible with `python -m prompt_model.reporting <trace_path>`.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=False),
            _JsonlTee(trace_path),
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO+
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


_log = structlog.get_logger()


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


_DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"
_DEFAULT_ITERATIONS = 8
_DEFAULT_CONCURRENCY = 4


async def amain() -> int:
    parser = argparse.ArgumentParser(
        prog="prompt-forge-self-improvement",
        description="Optimize prompt-forge's own internal LLM prompts.",
    )
    parser.add_argument(
        "--target",
        required=True,
        choices=sorted(REGISTRY.keys()),
        metavar="TARGET",
        help=f"Which internal prompt to optimize. Available: {', '.join(sorted(REGISTRY.keys()))}",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path to write the optimized prompt markdown file.",
    )
    parser.add_argument(
        "--model",
        default=_DEFAULT_MODEL,
        help=f"LiteLLM model string used for target, actor, and judge. Default: {_DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=_DEFAULT_ITERATIONS,
        help=f"Number of optimization iterations. Default: {_DEFAULT_ITERATIONS}",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=_DEFAULT_CONCURRENCY,
        help=f"Max concurrent LLM calls. Default: {_DEFAULT_CONCURRENCY}",
    )

    args = parser.parse_args()
    _clear_llm_call_logs()
    target = REGISTRY[args.target]

    # Auto-derive the trace path alongside the output file.
    # The JSONL log is compatible with: python -m prompt_model.reporting <trace_path>
    trace_path: Path = args.output.with_suffix(".jsonl")
    _configure_logging(trace_path)

    print(f"Target  : {target.name}")
    print(f"  {target.description}")
    print(f"Model   : {args.model}")
    print(f"Iters   : {args.iterations}  |  Concurrency: {args.concurrency}")
    print(f"Output  : {args.output}")
    print(f"Trace   : {trace_path}")
    print()

    result = await run_target(
        target=target,
        output_path=args.output,
        model=args.model,
        iterations=args.iterations,
        concurrency=args.concurrency,
    )

    print(f"\nDone in {result.iterations_run} iteration(s).  Best score: {result.best_score:.4f}")
    print(f"Optimized prompt written to: {args.output}")
    return 0


def main() -> int:
    try:
        return asyncio.run(amain())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 1
    except Exception as exc:
        _log.error("optimization_failed", error=str(exc), exc_info=True)
        print(f"\nError: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
