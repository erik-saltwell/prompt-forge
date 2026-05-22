import asyncio
from typing import Any, ClassVar

import pytest
from prompt_model.llm import LiteLLMConfig
from prompt_model.metrics import BaseLLMJudgeMetric, MetricResult


class _StubJudge(BaseLLMJudgeMetric):
    name: ClassVar[str] = "stub_judge"
    description: ClassVar[str] = "A test judge"

    def build_messages(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> list[dict[str, Any]]:
        return [{"role": "user", "content": f"{prompt}|{input}|{output}|{ground_truth}"}]

    def parse_result(self, raw_text: str) -> MetricResult:
        return MetricResult(metric_name="wrong-name-on-purpose", score=float(raw_text), assessment="parsed")


def test_evaluate_stamps_metric_name(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_acomplete(config: LiteLLMConfig, messages: list[dict[str, Any]]) -> str:
        assert config.model == "fake/model"
        assert messages[0]["content"].startswith("prompt-text|")
        return "0.75"

    monkeypatch.setattr("prompt_model.metrics.base_llm_judge.acomplete", fake_acomplete)

    judge: _StubJudge = _StubJudge(LiteLLMConfig(model="fake/model"))
    result: MetricResult = asyncio.run(judge.evaluate("prompt-text", "input-text", "output-text", None))
    assert result.metric_name == "stub_judge"
    assert result.score == 0.75
    assert result.assessment == "parsed"
