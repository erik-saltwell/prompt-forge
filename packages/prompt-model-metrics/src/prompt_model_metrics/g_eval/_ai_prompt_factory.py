from __future__ import annotations

import threading
from collections import defaultdict

from cachetools import LRUCache
from prompt_model.config import LiteLLMConfig
from prompt_model.helpers import acomplete

from ._prompt_context import SCORE_MAX, SCORE_MIN, PromptContext, PromptContextDraft
from ._resources import render_template

_CACHE_MAXSIZE: int = 256
_CACHE_VERSION: int = 1

type _CacheKey = tuple[int, str, str]

_cache: LRUCache[_CacheKey, PromptContext] = LRUCache(maxsize=_CACHE_MAXSIZE)
_cache_lock: threading.Lock = threading.Lock()
_key_locks: defaultdict[_CacheKey, threading.Lock] = defaultdict(threading.Lock)
_key_locks_lock: threading.Lock = threading.Lock()


def _make_key(criterion: str, llm_config: LiteLLMConfig) -> _CacheKey:
    return (_CACHE_VERSION, criterion, llm_config.model)


def _get_key_lock(key: _CacheKey) -> threading.Lock:
    with _key_locks_lock:
        return _key_locks[key]


def _cache_get(key: _CacheKey) -> PromptContext | None:
    with _cache_lock:
        return _cache.get(key)


def _cache_put(key: _CacheKey, value: PromptContext) -> None:
    with _cache_lock:
        _cache[key] = value


def reset_cache() -> None:
    """Clear the PromptContext cache. Test-only seam."""
    with _cache_lock:
        _cache.clear()
    with _key_locks_lock:
        _key_locks.clear()


async def create_prompt_context(criterion: str, llm_config: LiteLLMConfig) -> PromptContext:
    """Get or build the PromptContext for a criterion.

    Thread-safe: same-key requests serialise on one LLM call; different-key requests
    run in parallel.
    """
    key: _CacheKey = _make_key(criterion, llm_config)
    cached: PromptContext | None = _cache_get(key)
    if cached is not None:
        return cached

    key_lock: threading.Lock = _get_key_lock(key)
    with key_lock:
        cached = _cache_get(key)
        if cached is not None:
            return cached

        system_prompt: str = render_template(
            "context_factory_prompt",
            score_min=SCORE_MIN,
            score_max=SCORE_MAX,
            criterion=criterion,
        )
        draft: PromptContextDraft = await acomplete(
            system_prompt=system_prompt,
            user_prompt=criterion,
            config=llm_config,
            response_format=PromptContextDraft,
            log_name="g_eval:context_factory",
        )
        context: PromptContext = draft.to_context(criterion)
        _cache_put(key, context)
        return context
