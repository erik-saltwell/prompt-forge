import asyncio
from typing import ClassVar

import pytest
from prompt_model import BaseLLMJudgeMetric, MetricResult
from prompt_model._metrics.base_llm_judge import _PromptPair
from prompt_model.config import LiteLLMConfig


class _StubJudge(BaseLLMJudgeMetric):
    name: ClassVar[str] = "stub_judge"
    description: ClassVar[str] = "A test judge"

    def build_messages(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> _PromptPair:
        return _PromptPair(system_prompt="sys", user_prompt=f"{prompt}|{input}|{output}|{ground_truth}")

    def parse_result(self, raw_text: str) -> MetricResult:
        return MetricResult(metric_name="wrong-name-on-purpose", score=float(raw_text), assessment="parsed")


def test_evaluate_stamps_metric_name(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_acomplete(system_prompt: str, user_prompt: str, config: LiteLLMConfig) -> str:
        assert config.model == "fake/model"
        assert user_prompt.startswith("prompt-text|")
        return "0.75"

    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", fake_acomplete)

    judge: _StubJudge = _StubJudge(LiteLLMConfig(model="fake/model"))
    result: MetricResult = asyncio.run(judge.evaluate("prompt-text", "input-text", "output-text", None))
    assert result.metric_name == "stub_judge"
    assert result.score == 0.75
    assert result.assessment == "parsed"
