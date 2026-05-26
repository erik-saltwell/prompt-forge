"""CLI entry point for prompt-forge-self-improvement."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import structlog
import structlog.dev

from ._registry import REGISTRY
from ._runner import run_target


def _configure_logging() -> None:
    """Route structlog output to stderr so it is visible without PYTHONUNBUFFERED."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=False),
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO+
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


_log = structlog.get_logger()

_DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"
_DEFAULT_ITERATIONS = 8
_DEFAULT_CONCURRENCY = 4


async def amain() -> int:
    _configure_logging()
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
    target = REGISTRY[args.target]

    print(f"Target  : {target.name}")
    print(f"  {target.description}")
    print(f"Model   : {args.model}")
    print(f"Iters   : {args.iterations}  |  Concurrency: {args.concurrency}")
    print(f"Output  : {args.output}")
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
