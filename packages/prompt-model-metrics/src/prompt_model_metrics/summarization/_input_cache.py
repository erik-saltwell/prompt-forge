from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import cachetools
from prompt_model.config import LiteLLMConfig
from prompt_model.helpers import acomplete

from ._resources import render_prompt_resource
from .prompt_schemas import PromptClaims, PromptQuestions

MAX_SIZE: int = 500


@dataclass
class InputData:
    truths: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)


_cache_lock: asyncio.Lock = asyncio.Lock()
_cache: cachetools.LRUCache[str, InputData] = cachetools.LRUCache(maxsize=MAX_SIZE)
_in_flight: dict[str, asyncio.Task[InputData]] = {}


def estimate_question_count(text: str) -> int:
    words = len(text.split())

    if words < 250:
        return 5
    if words < 750:
        return 10
    if words < 1500:
        return 15
    if words < 3000:
        return 25
    return 40


async def _generate_truths_from_claims(input: str, litellm_config: LiteLLMConfig) -> PromptClaims:
    return await acomplete(
        system_prompt=render_prompt_resource("generate_claims"),
        user_prompt=f"<input>\n{input}\n</input>",
        config=litellm_config,
        response_format=PromptClaims,
        log_name="summary_input_cache:claims",
    )


async def _generate_questions_from_input(input: str, litellm_config: LiteLLMConfig) -> PromptQuestions:
    return await acomplete(
        system_prompt=render_prompt_resource("generate_questions", max_question_count=estimate_question_count(input)),
        user_prompt=f"<input>\n{input}\n</input>",
        config=litellm_config,
        response_format=PromptQuestions,
        log_name="summary_input_cache:questions",
    )


async def _create_input_data(input: str, litellm_config: LiteLLMConfig) -> InputData:
    truths: list[str] = (await _generate_truths_from_claims(input, litellm_config)).claims
    questions: list[str] = (await _generate_questions_from_input(input, litellm_config)).questions
    return InputData(truths, questions)


async def _discard_in_flight(input: str) -> None:
    async with _cache_lock:
        _in_flight.pop(input, None)


async def _create_and_cache(input: str, litellm_config: LiteLLMConfig) -> InputData:
    try:
        input_data: InputData = await _create_input_data(input, litellm_config)
    except asyncio.CancelledError:
        await _discard_in_flight(input)
        raise
    except Exception:
        await _discard_in_flight(input)
        raise

    async with _cache_lock:
        _cache[input] = input_data
        _in_flight.pop(input, None)
    return input_data


async def get_or_add(input: str, litellm_config: LiteLLMConfig) -> InputData:
    async with _cache_lock:
        cached: InputData | None = _cache.get(input)
        if cached is not None:
            return cached

        task: asyncio.Task[InputData] | None = _in_flight.get(input)
        if task is None:
            task = asyncio.create_task(_create_and_cache(input, litellm_config))
            _in_flight[input] = task

    return await asyncio.shield(task)


async def reset_cache() -> None:
    """Clear the input cache. Test-only seam."""
    async with _cache_lock:
        tasks: list[asyncio.Task[InputData]] = list(_in_flight.values())
        _cache.clear()
        _in_flight.clear()

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
