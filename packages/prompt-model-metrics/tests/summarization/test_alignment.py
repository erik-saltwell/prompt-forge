from __future__ import annotations

import asyncio
from typing import Any

from prompt_model.config import LiteLLMConfig
from prompt_model_metrics.summarization import _input_cache, alignment
from prompt_model_metrics.summarization.prompt_schemas import (
    ClaimVerdict,
    ClaimVerdicts,
    FailureTypeStr,
    PromptClaims,
    PromptQuestions,
)

_CONFIG = LiteLLMConfig(model="fake/model")

_PROMPT = "# Summarize\n\nWrite a concise summary of the input."
_INPUT = "Alice founded Acme in 2010. The company grew to 500 employees by 2020."
_OUTPUT_FAITHFUL = "Alice started Acme in 2010, which reached 500 staff by 2020."
_OUTPUT_HALLUCINATED = "Alice founded Acme in 2015 and it has 1000 employees today."


def _yes(claim: str) -> ClaimVerdict:
    return ClaimVerdict(claim=claim, supported="yes", failure_type=None)


def _no(
    claim: str,
    rationale: str,
    culprit_node_id: str,
    conflicting_input_claim: str | None,
    failure_type: FailureTypeStr = "contradiction",
    suggested_prompt_change: str | None = None,
) -> ClaimVerdict:
    return ClaimVerdict(
        claim=claim,
        supported="no",
        failure_type=failure_type,
        rationale=rationale,
        culprit_node_id=culprit_node_id,
        conflicting_input_claim=conflicting_input_claim,
        suggested_prompt_change=suggested_prompt_change,
    )


def _make_fake_acomplete(
    input_claims: list[str],
    output_claims: list[str],
    verdicts: ClaimVerdicts,
) -> Any:
    async def fake_acomplete(
        system_prompt: str,
        user_prompt: str,
        config: LiteLLMConfig,
        *,
        response_format: type[object] | None = None,
        log_name: str | None = None,
    ) -> object:
        if response_format is PromptClaims:
            if "summary_alignment:output_claims" in (log_name or ""):
                return PromptClaims(claims=output_claims)
            return PromptClaims(claims=input_claims)
        if response_format is PromptQuestions:
            return PromptQuestions(questions=["Did Alice found Acme in 2010?"])
        if response_format is ClaimVerdicts:
            return verdicts
        raise AssertionError(f"unexpected response_format: {response_format}")

    return fake_acomplete


def test_all_faithful_returns_score_1_and_no_signals(monkeypatch: Any) -> None:
    verdicts = ClaimVerdicts(
        verdicts=[
            _yes("Alice started Acme in 2010."),
            _yes("Acme reached 500 staff by 2020."),
        ]
    )
    fake = _make_fake_acomplete(
        input_claims=["Alice founded Acme in 2010.", "The company grew to 500 employees by 2020."],
        output_claims=["Alice started Acme in 2010.", "Acme reached 500 staff by 2020."],
        verdicts=verdicts,
    )
    monkeypatch.setattr(_input_cache, "acomplete", fake)
    monkeypatch.setattr(alignment, "acomplete", fake)

    metric = alignment.AlignmentMetric(_CONFIG)
    result = asyncio.run(metric.evaluate(_PROMPT, _INPUT, _OUTPUT_FAITHFUL, None))

    assert result.metric_name == "summary_alignment"
    assert result.score == 1.0
    assert result.signals == []
    assert "2" in result.assessment


def test_hallucinated_claim_returns_signal_with_culprit(monkeypatch: Any) -> None:
    verdicts = ClaimVerdicts(
        verdicts=[
            _no(
                claim="Alice founded Acme in 2015.",
                rationale="Source says Acme was founded in 2010, not 2015.",
                culprit_node_id="1.1",
                conflicting_input_claim="Alice founded Acme in 2010.",
                suggested_prompt_change="Instruct the model to preserve exact dates from the source.",
            ),
            _no(
                claim="Acme has 1000 employees today.",
                rationale="Source says 500 employees.",
                culprit_node_id="document",
                conflicting_input_claim="The company grew to 500 employees by 2020.",
                failure_type="contradiction",
            ),
        ]
    )
    fake = _make_fake_acomplete(
        input_claims=["Alice founded Acme in 2010.", "The company grew to 500 employees by 2020."],
        output_claims=["Alice founded Acme in 2015.", "Acme has 1000 employees today."],
        verdicts=verdicts,
    )
    monkeypatch.setattr(_input_cache, "acomplete", fake)
    monkeypatch.setattr(alignment, "acomplete", fake)

    metric = alignment.AlignmentMetric(_CONFIG)
    result = asyncio.run(metric.evaluate(_PROMPT, _INPUT, _OUTPUT_HALLUCINATED, None))

    assert result.metric_name == "summary_alignment"
    assert result.score == 0.0
    assert len(result.signals) == 2

    s0 = result.signals[0]
    assert s0.culprit_node_id == "1.1"
    assert s0.input_snippet == "Alice founded Acme in 2010."
    assert s0.output_snippet == "Alice founded Acme in 2015."
    assert s0.suggested_prompt_change == "Instruct the model to preserve exact dates from the source."

    s1 = result.signals[1]
    assert s1.culprit_node_id == "document"
    assert s1.suggested_prompt_change is None


def test_empty_output_claims_returns_score_0_with_document_signal(monkeypatch: Any) -> None:
    async def fake_acomplete(
        system_prompt: str,
        user_prompt: str,
        config: LiteLLMConfig,
        *,
        response_format: type[object] | None = None,
        log_name: str | None = None,
    ) -> object:
        if response_format is PromptClaims:
            if "summary_alignment:output_claims" in (log_name or ""):
                return PromptClaims(claims=[])
            return PromptClaims(claims=["Alice founded Acme in 2010."])
        if response_format is PromptQuestions:
            return PromptQuestions(questions=["Did Alice found Acme?"])
        raise AssertionError(f"unexpected response_format: {response_format}")

    monkeypatch.setattr(_input_cache, "acomplete", fake_acomplete)
    monkeypatch.setattr(alignment, "acomplete", fake_acomplete)

    metric = alignment.AlignmentMetric(_CONFIG)
    result = asyncio.run(metric.evaluate(_PROMPT, _INPUT, "", None))

    assert result.score == 0.0
    assert len(result.signals) == 1
    assert result.signals[0].culprit_node_id == "document"


def test_verdict_count_mismatch_returns_score_0_with_document_signal(monkeypatch: Any) -> None:
    # scorer returns one verdict for two output claims → mismatch
    verdicts = ClaimVerdicts(verdicts=[_yes("Alice started Acme in 2010.")])
    fake = _make_fake_acomplete(
        input_claims=["Alice founded Acme in 2010.", "500 employees by 2020."],
        output_claims=["Alice started Acme in 2010.", "Acme reached 500 staff by 2020."],
        verdicts=verdicts,
    )
    monkeypatch.setattr(_input_cache, "acomplete", fake)
    monkeypatch.setattr(alignment, "acomplete", fake)

    metric = alignment.AlignmentMetric(_CONFIG)
    result = asyncio.run(metric.evaluate(_PROMPT, _INPUT, _OUTPUT_FAITHFUL, None))

    assert result.score == 0.0
    assert len(result.signals) == 1
    assert result.signals[0].culprit_node_id == "document"


def test_render_strategy_is_used_for_prompt_and_format_description(monkeypatch: Any) -> None:
    """Custom render strategy's render() and describe_format() are both called."""
    render_calls: list[str] = []
    describe_calls: list[str] = []

    class FakeStrategy:
        def render(self, tree: object, focus_ids: object) -> str:
            render_calls.append("render")
            return "<fake>rendered</fake>"

        def describe_format(self) -> str:
            describe_calls.append("describe")
            return "Nodes are identified by their `id` attribute."

    verdicts = ClaimVerdicts(verdicts=[_yes("Alice started Acme.")])
    scorer_prompts: list[str] = []

    async def fake_acomplete(
        system_prompt: str,
        user_prompt: str,
        config: LiteLLMConfig,
        *,
        response_format: type[object] | None = None,
        log_name: str | None = None,
    ) -> object:
        if response_format is PromptClaims:
            if "summary_alignment:output_claims" in (log_name or ""):
                return PromptClaims(claims=["Alice started Acme."])
            return PromptClaims(claims=["Alice founded Acme in 2010."])
        if response_format is PromptQuestions:
            return PromptQuestions(questions=["Did Alice found Acme?"])
        if response_format is ClaimVerdicts:
            scorer_prompts.append(system_prompt)
            scorer_prompts.append(user_prompt)
            return verdicts
        raise AssertionError(f"unexpected response_format: {response_format}")

    monkeypatch.setattr(_input_cache, "acomplete", fake_acomplete)
    monkeypatch.setattr(alignment, "acomplete", fake_acomplete)

    metric = alignment.AlignmentMetric(_CONFIG, render_strategy=FakeStrategy())  # type: ignore[arg-type]
    asyncio.run(metric.evaluate(_PROMPT, _INPUT, "Alice started Acme.", None))

    assert render_calls == ["render"]
    assert describe_calls == ["describe"]
    assert "<fake>rendered</fake>" in scorer_prompts[1]
    assert "Nodes are identified by their `id` attribute." in scorer_prompts[0]
