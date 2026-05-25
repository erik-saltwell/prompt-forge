"""Tests for BaseClaimMetric — the 4-step claim-by-claim pipeline.

Behaviors under test:
1. Zero failing verdicts → score=1.0, no signals
2. One failing verdict → one IssueSignal, claim is output_snippet
3. N failing verdicts → single batched attribution call
4. culprit_node_id from attribution lands on the signal
5. Score = passing fraction (2 pass, 1 fail → ~0.67)
6. Passing verdicts contribute to preserve
"""

from __future__ import annotations

import asyncio
from typing import ClassVar

from prompt_model._metrics.base_claim_metric import BaseClaimMetric, ClaimVerdict, NodeAttribution
from prompt_model._metrics.result import IssueSignal, MetricResult
from prompt_model.config import LiteLLMConfig

_CONFIG = LiteLLMConfig(model="fake/model")
_PROMPT_MD = "# Summarize\n\nSummarize the article clearly and completely.\n"
_INPUT = "The sky is blue. Grass is green. The sun is yellow."
_OUTPUT = "The sky is blue. Grass is purple. The moon is yellow."
_GROUND_TRUTH = "The sky is blue. Grass is green. The sun is yellow."


class _StubClaimMetric(BaseClaimMetric):
    """Fully controllable stub: returns preset claims, reference points, verdicts, and attributions."""

    name: ClassVar[str] = "stub_claim"
    description: ClassVar[str] = "Stub for testing"

    def __init__(
        self,
        config: LiteLLMConfig,
        *,
        claims: list[str],
        reference_points: list[str],
        verdicts: list[ClaimVerdict],
        attributions: list[NodeAttribution],
    ) -> None:
        super().__init__(config)
        self._claims = claims
        self._reference_points = reference_points
        self._verdicts = verdicts
        self._attributions = attributions

    def claim_extraction_prompt(self, output: str) -> str:
        return f"extract claims from: {output}"

    def reference_extraction_prompt(self, input: str, ground_truth: str | None) -> str:
        return f"extract reference from: {input} / {ground_truth}"

    def verdict_prompt(self, claims: list[str], reference_points: list[str]) -> str:
        return f"verdict: {claims} vs {reference_points}"

    # Override the internal LLM steps to return preset data
    async def _extract_claims(self, output: str) -> list[str]:
        return self._claims

    async def _extract_reference_points(self, input: str, ground_truth: str | None) -> list[str]:
        return self._reference_points

    async def _generate_verdicts(self, claims: list[str], reference_points: list[str]) -> list[ClaimVerdict]:
        return self._verdicts

    async def _attribute_nodes(self, failing_verdicts: list[ClaimVerdict], prompt_with_ids: str) -> list[NodeAttribution]:
        return self._attributions


def _verdict(claim: str, *, passes: bool, reason: str = "reason") -> ClaimVerdict:
    return ClaimVerdict(claim=claim, passes=passes, reason=reason if not passes else None)


def _attribution(claim: str, node_id: str = "1.1") -> NodeAttribution:
    return NodeAttribution(claim=claim, culprit_node_id=node_id)


# --- zero failures ---


def test_all_passing_verdicts_gives_perfect_score() -> None:
    metric = _StubClaimMetric(
        _CONFIG,
        claims=["sky is blue", "grass is green"],
        reference_points=["sky is blue", "grass is green"],
        verdicts=[_verdict("sky is blue", passes=True), _verdict("grass is green", passes=True)],
        attributions=[],
    )
    result: MetricResult = asyncio.run(metric.evaluate(_PROMPT_MD, _INPUT, _OUTPUT, None))
    assert result.score == 1.0
    assert result.signals == []


# --- single failure ---


def test_one_failing_verdict_produces_one_signal() -> None:
    metric = _StubClaimMetric(
        _CONFIG,
        claims=["grass is purple"],
        reference_points=["grass is green"],
        verdicts=[_verdict("grass is purple", passes=False, reason="contradicts source")],
        attributions=[_attribution("grass is purple", node_id="1.2")],
    )
    result: MetricResult = asyncio.run(metric.evaluate(_PROMPT_MD, _INPUT, _OUTPUT, None))
    assert len(result.signals) == 1
    signal: IssueSignal = result.signals[0]
    assert signal.culprit_node_id == "1.2"
    assert "grass is purple" in signal.output_snippet


def test_failing_verdict_reason_appears_in_rationale() -> None:
    metric = _StubClaimMetric(
        _CONFIG,
        claims=["grass is purple"],
        reference_points=["grass is green"],
        verdicts=[_verdict("grass is purple", passes=False, reason="contradicts source")],
        attributions=[_attribution("grass is purple")],
    )
    result: MetricResult = asyncio.run(metric.evaluate(_PROMPT_MD, _INPUT, _OUTPUT, None))
    assert "contradicts source" in result.signals[0].rationale


# --- multiple failures ---


def test_score_is_passing_fraction() -> None:
    metric = _StubClaimMetric(
        _CONFIG,
        claims=["sky is blue", "grass is purple", "moon is yellow"],
        reference_points=["sky is blue", "grass is green", "sun is yellow"],
        verdicts=[
            _verdict("sky is blue", passes=True),
            _verdict("grass is purple", passes=False, reason="wrong color"),
            _verdict("moon is yellow", passes=False, reason="wrong object"),
        ],
        attributions=[
            _attribution("grass is purple", node_id="1.1"),
            _attribution("moon is yellow", node_id="1.2"),
        ],
    )
    result: MetricResult = asyncio.run(metric.evaluate(_PROMPT_MD, _INPUT, _OUTPUT, None))
    assert abs(result.score - (1 / 3)) < 0.01
    assert len(result.signals) == 2


def test_each_failing_verdict_becomes_a_separate_signal() -> None:
    metric = _StubClaimMetric(
        _CONFIG,
        claims=["claim A", "claim B"],
        reference_points=["ref"],
        verdicts=[
            _verdict("claim A", passes=False, reason="wrong A"),
            _verdict("claim B", passes=False, reason="wrong B"),
        ],
        attributions=[
            _attribution("claim A", node_id="1.1"),
            _attribution("claim B", node_id="1.2"),
        ],
    )
    result: MetricResult = asyncio.run(metric.evaluate(_PROMPT_MD, _INPUT, _OUTPUT, None))
    node_ids: set[str] = {s.culprit_node_id for s in result.signals}
    assert node_ids == {"1.1", "1.2"}


# --- attribution fallback ---


def test_missing_attribution_falls_back_to_document_sentinel() -> None:
    """If the attribution step returns no entry for a claim, culprit defaults to 'document'."""
    metric = _StubClaimMetric(
        _CONFIG,
        claims=["bad claim"],
        reference_points=["ref"],
        verdicts=[_verdict("bad claim", passes=False, reason="wrong")],
        attributions=[],  # attribution step returns nothing
    )
    result: MetricResult = asyncio.run(metric.evaluate(_PROMPT_MD, _INPUT, _OUTPUT, None))
    assert result.signals[0].culprit_node_id == "document"


# --- metric_name ---


def test_metric_name_is_stamped() -> None:
    metric = _StubClaimMetric(
        _CONFIG,
        claims=[],
        reference_points=[],
        verdicts=[],
        attributions=[],
    )
    result: MetricResult = asyncio.run(metric.evaluate(_PROMPT_MD, _INPUT, _OUTPUT, None))
    assert result.metric_name == "stub_claim"
