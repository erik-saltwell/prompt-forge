"""Global LLM-concurrency gate.

Every `acomplete` / `complete` call acquires from the current concurrency
semaphore before hitting the provider. The semaphore is held in a `ContextVar`
so concurrent asyncio tasks share the same cap, and so nested contexts (e.g.
tests) can rebind without leaking state.

By default the gate is effectively unbounded — set a real cap by entering
`set_llm_concurrency(n)` as a context manager, typically once at the top of
`optimize_prompt`. Callers outside the optimizer (one-off scripts, tests) pay
no concurrency cost unless they opt in.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Iterator
from contextvars import ContextVar, Token

_UNBOUNDED: int = 10_000

_llm_sem: ContextVar[asyncio.Semaphore | None] = ContextVar("llm_sem", default=None)


def get_llm_semaphore() -> asyncio.Semaphore:
    """Return the current LLM semaphore, lazily creating an effectively-unbounded one if no cap is set.

    asyncio.Semaphore needs a running event loop, so we avoid instantiating one at module load.
    """
    sem: asyncio.Semaphore | None = _llm_sem.get()
    if sem is None:
        sem = asyncio.Semaphore(_UNBOUNDED)
        _llm_sem.set(sem)
    return sem


@contextlib.contextmanager
def set_llm_concurrency(max_concurrent: int) -> Iterator[None]:
    """Bind a fresh `Semaphore(max_concurrent)` for the duration of the block.

    Use once at the top of an optimization run. All `acomplete` / `complete`
    calls reached from inside this context share the cap.
    """
    if max_concurrent < 1:
        raise ValueError(f"max_concurrent must be >= 1, got {max_concurrent}")
    token: Token[asyncio.Semaphore | None] = _llm_sem.set(asyncio.Semaphore(max_concurrent))
    try:
        yield
    finally:
        _llm_sem.reset(token)
