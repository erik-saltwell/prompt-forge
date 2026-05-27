from __future__ import annotations

import asyncio
from typing import Any

import pytest
from prompt_model.config import LiteLLMConfig
from prompt_model_metrics.summarization import _input_cache
from prompt_model_metrics.summarization.prompt_schemas import PromptClaims, PromptQuestions

_CONFIG = LiteLLMConfig(model="fake/model")


@pytest.fixture(autouse=True)
def clear_input_cache() -> None:
    asyncio.run(_input_cache.reset_cache())


def test_create_input_data_uses_prompt_resources_and_structured_outputs(monkeypatch: Any) -> None:
    calls: list[dict[str, object]] = []

    async def fake_acomplete(
        system_prompt: str,
        user_prompt: str,
        config: LiteLLMConfig,
        *,
        response_format: type[object] | None = None,
        log_name: str | None = None,
    ) -> object:
        calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "config": config,
                "response_format": response_format,
                "log_name": log_name,
            }
        )
        if response_format is PromptClaims:
            return PromptClaims(claims=["Claim one."])
        if response_format is PromptQuestions:
            return PromptQuestions(questions=["Did claim one happen?"])
        raise AssertionError(f"unexpected response_format: {response_format}")

    monkeypatch.setattr(_input_cache, "acomplete", fake_acomplete)

    result = asyncio.run(_input_cache._create_input_data("source text", _CONFIG))

    assert result.truths == ["Claim one."]
    assert result.questions == ["Did claim one happen?"]
    assert [call["response_format"] for call in calls] == [PromptClaims, PromptQuestions]
    assert "{{ max_question_count }}" not in str(calls[1]["system_prompt"])
    assert "source text" in str(calls[0]["user_prompt"])


def test_get_or_add_shares_concurrent_generation_for_same_input(monkeypatch: Any) -> None:
    calls: list[type[object] | None] = []

    async def fake_acomplete(
        system_prompt: str,
        user_prompt: str,
        config: LiteLLMConfig,
        *,
        response_format: type[object] | None = None,
        log_name: str | None = None,
    ) -> object:
        calls.append(response_format)
        await asyncio.sleep(0)
        if response_format is PromptClaims:
            return PromptClaims(claims=["shared claim"])
        if response_format is PromptQuestions:
            return PromptQuestions(questions=["shared question"])
        raise AssertionError(f"unexpected response_format: {response_format}")

    async def run_concurrent_calls() -> list[_input_cache.InputData]:
        return await asyncio.gather(*[_input_cache.get_or_add("shared source", _CONFIG) for _ in range(5)])

    monkeypatch.setattr(_input_cache, "acomplete", fake_acomplete)

    results = asyncio.run(run_concurrent_calls())

    assert [result.truths for result in results] == [["shared claim"]] * 5
    assert calls == [PromptClaims, PromptQuestions]
    assert _input_cache._in_flight == {}


def test_get_or_add_allows_different_inputs_to_generate_concurrently(monkeypatch: Any) -> None:
    claim_calls_started: list[str] = []

    async def run_concurrent_calls() -> tuple[_input_cache.InputData, _input_cache.InputData]:
        both_claim_calls_started = asyncio.Event()

        async def fake_acomplete(
            system_prompt: str,
            user_prompt: str,
            config: LiteLLMConfig,
            *,
            response_format: type[object] | None = None,
            log_name: str | None = None,
        ) -> object:
            if response_format is PromptClaims:
                claim_calls_started.append(user_prompt)
                if len(claim_calls_started) == 2:
                    both_claim_calls_started.set()
                await asyncio.wait_for(both_claim_calls_started.wait(), timeout=1)
                return PromptClaims(claims=[user_prompt])
            if response_format is PromptQuestions:
                return PromptQuestions(questions=[user_prompt])
            raise AssertionError(f"unexpected response_format: {response_format}")

        monkeypatch.setattr(_input_cache, "acomplete", fake_acomplete)

        return await asyncio.gather(
            _input_cache.get_or_add("source one", _CONFIG),
            _input_cache.get_or_add("source two", _CONFIG),
        )

    results = asyncio.run(run_concurrent_calls())

    assert len(claim_calls_started) == 2
    assert [result.truths[0] for result in results] == [
        "<input>\nsource one\n</input>",
        "<input>\nsource two\n</input>",
    ]
    assert _input_cache._in_flight == {}
