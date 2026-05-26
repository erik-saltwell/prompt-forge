"""Tests for the redesigned BaseLLMJudgeMetric.

Public interface under test:
- __init__(litellm_config, render_strategy=None)
- build_system_prompt() -> str  [abstract, subclass provides]
- build_user_prompt(rendered_prompt, input, output, ground_truth) -> str  [optional override]
- evaluate(prompt, input, output, ground_truth) -> MetricResult
"""

from __future__ import annotations

import asyncio
from typing import ClassVar

import pytest
from prompt_model import BaseLLMJudgeMetric, MetricResult
from prompt_model._prompt import Document
from prompt_model.config import LiteLLMConfig
from prompt_model.strategies.prompt_rendering_strategy import MarkdownRenderPromptStrategy

_CONFIG = LiteLLMConfig(model="fake/model")

_PROMPT_MD = "# Summarize\n\nSummarize the input concisely.\n"

_RESULT = MetricResult(
    metric_name="wrong-on-purpose",
    score=0.8,
    assessment="looks good",
)


class _StubJudge(BaseLLMJudgeMetric):
    name: ClassVar[str] = "stub_judge"
    description: ClassVar[str] = "A test judge"

    def build_system_prompt(self) -> str:
        return "You are a judge."


class _CustomUserPromptJudge(BaseLLMJudgeMetric):
    name: ClassVar[str] = "custom_user_prompt_judge"
    description: ClassVar[str] = "Judge with custom user prompt"
    captured_args: tuple[str, str, str, str | None] | None = None

    def build_system_prompt(self) -> str:
        return "sys"

    def build_user_prompt(self, rendered_prompt: str, input: str, output: str, ground_truth: str | None) -> str:
        _CustomUserPromptJudge.captured_args = (rendered_prompt, input, output, ground_truth)
        return f"CUSTOM:{rendered_prompt}|{input}|{output}|{ground_truth}"


class _RecordingRenderStrategy:
    """Captures the Document passed to render() for assertion."""

    def __init__(self) -> None:
        self.calls: list[tuple[Document, set[str] | None]] = []

    def render(self, tree: Document, focus_ids: set[str] | None) -> str:
        self.calls.append((tree, focus_ids))
        return "RENDERED"

    def describe_format(self) -> str:
        return "recording format"


def _make_acomplete_stub(result: MetricResult = _RESULT):
    async def _stub(system_prompt: str, user_prompt: str, config: LiteLLMConfig, *, response_format=None, log_name: str | None = None):
        return result

    return _stub


# --- metric_name stamping ---


def test_evaluate_stamps_metric_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", _make_acomplete_stub())
    result: MetricResult = asyncio.run(_StubJudge(_CONFIG).evaluate(_PROMPT_MD, "input", "output", None))
    assert result.metric_name == "stub_judge"


def test_evaluate_preserves_score_and_assessment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", _make_acomplete_stub())
    result: MetricResult = asyncio.run(_StubJudge(_CONFIG).evaluate(_PROMPT_MD, "input", "output", None))
    assert result.score == 0.8
    assert result.assessment == "looks good"


# --- render strategy ---


def test_default_render_strategy_is_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", _make_acomplete_stub())
    assert isinstance(_StubJudge(_CONFIG).render_strategy, MarkdownRenderPromptStrategy)


def test_injected_render_strategy_is_called(monkeypatch: pytest.MonkeyPatch) -> None:
    recording = _RecordingRenderStrategy()
    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", _make_acomplete_stub())
    asyncio.run(_StubJudge(_CONFIG, render_strategy=recording).evaluate(_PROMPT_MD, "input", "output", None))
    assert len(recording.calls) == 1
    doc, focus_ids = recording.calls[0]
    assert isinstance(doc, Document)
    assert focus_ids is None


def test_render_strategy_output_reaches_user_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    recording = _RecordingRenderStrategy()
    captured: list[str] = []

    async def _stub(system_prompt: str, user_prompt: str, config: LiteLLMConfig, *, response_format=None, log_name=None):
        captured.append(user_prompt)
        return _RESULT

    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", _stub)
    asyncio.run(_StubJudge(_CONFIG, render_strategy=recording).evaluate(_PROMPT_MD, "input", "output", None))
    assert "RENDERED" in captured[0]


# --- structured output ---


def test_evaluate_calls_acomplete_with_metric_result_response_format(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_kwargs: list[dict] = []

    async def _stub(system_prompt: str, user_prompt: str, config: LiteLLMConfig, *, response_format=None, log_name=None):
        captured_kwargs.append({"response_format": response_format})
        return _RESULT

    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", _stub)
    asyncio.run(_StubJudge(_CONFIG).evaluate(_PROMPT_MD, "input", "output", None))
    assert captured_kwargs[0]["response_format"] is MetricResult


# --- system prompt ---


def test_build_system_prompt_is_passed_to_acomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    async def _stub(system_prompt: str, user_prompt: str, config: LiteLLMConfig, *, response_format=None, log_name=None):
        captured.append(system_prompt)
        return _RESULT

    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", _stub)
    asyncio.run(_StubJudge(_CONFIG).evaluate(_PROMPT_MD, "input", "output", None))
    assert captured[0] == "You are a judge."


# --- default user prompt layout ---


def test_default_user_prompt_contains_standard_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    async def _stub(system_prompt: str, user_prompt: str, config: LiteLLMConfig, *, response_format=None, log_name=None):
        captured.append(user_prompt)
        return _RESULT

    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", _stub)
    asyncio.run(_StubJudge(_CONFIG).evaluate(_PROMPT_MD, "my input", "my output", None))
    assert "<prompt>" in captured[0]
    assert "<input>" in captured[0]
    assert "<output>" in captured[0]
    assert "my input" in captured[0]
    assert "my output" in captured[0]


def test_default_user_prompt_includes_ground_truth_when_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    async def _stub(system_prompt: str, user_prompt: str, config: LiteLLMConfig, *, response_format=None, log_name=None):
        captured.append(user_prompt)
        return _RESULT

    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", _stub)
    asyncio.run(_StubJudge(_CONFIG).evaluate(_PROMPT_MD, "input", "output", "reference answer"))
    assert "<ground_truth>" in captured[0]
    assert "reference answer" in captured[0]


def test_default_user_prompt_omits_ground_truth_block_when_none(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    async def _stub(system_prompt: str, user_prompt: str, config: LiteLLMConfig, *, response_format=None, log_name=None):
        captured.append(user_prompt)
        return _RESULT

    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", _stub)
    asyncio.run(_StubJudge(_CONFIG).evaluate(_PROMPT_MD, "input", "output", None))
    assert "<ground_truth>" not in captured[0]


# --- custom user prompt override ---


def test_custom_build_user_prompt_receives_rendered_prompt_and_args(monkeypatch: pytest.MonkeyPatch) -> None:
    recording = _RecordingRenderStrategy()
    monkeypatch.setattr("prompt_model._metrics.base_llm_judge.acomplete", _make_acomplete_stub())
    _CustomUserPromptJudge.captured_args = None
    asyncio.run(_CustomUserPromptJudge(_CONFIG, render_strategy=recording).evaluate(_PROMPT_MD, "inp", "out", "gt"))
    assert _CustomUserPromptJudge.captured_args is not None
    rendered, inp, out, gt = _CustomUserPromptJudge.captured_args
    assert rendered == "RENDERED"
    assert inp == "inp"
    assert out == "out"
    assert gt == "gt"
