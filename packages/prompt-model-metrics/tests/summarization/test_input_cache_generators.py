from __future__ import annotations

import asyncio
from typing import Any

from prompt_model.config import LiteLLMConfig
from prompt_model_metrics.summarization import _input_cache
from prompt_model_metrics.summarization.prompt_schemas import PromptClaims, PromptQuestions

_CONFIG = LiteLLMConfig(model="fake/model")


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
