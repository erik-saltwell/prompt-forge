"""CompletenessMetric — summarization completeness via key-point coverage.

Checks whether the output covers the key points from the ground_truth reference.
Tuned and validated for summarization tasks.
Reference source: `ground_truth` (the reference summary or key-point list).

Iteration is over **reference key points**, not output claims: for each key point in
the reference, the verdict step checks whether at least one output claim addresses it.
This is inverted from `AlignmentMetric`, which iterates over output claims and checks
each against the source — so several `BaseClaimMetric` hooks are overridden here.
"""

from __future__ import annotations

from typing import ClassVar

from prompt_model._metrics.base_claim_metric import BaseClaimMetric, ClaimVerdict
from prompt_model._metrics.protocol import MissingGroundTruthError
from prompt_model._metrics.result import IssueSignal, MetricResult
from prompt_model.config import LiteLLMConfig

from ._completeness_resources import load_completeness_resource


class CoverageMetric(BaseClaimMetric):
    """Checks that the output covers the key points from the ground_truth reference.

    Each key point from `ground_truth` is checked against the output claims.
    Omitted key points become `IssueSignal`s attributed to the prompt node most
    likely responsible for the omission.

    Requires `ground_truth`. Raises `MissingGroundTruthError` when it is `None`.
    """

    name: ClassVar[str] = "coverage"
    description: ClassVar[str] = "Checks that the output covers key points from the ground_truth reference (summarization)."

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        super().__init__(litellm_config)

    async def evaluate(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> MetricResult:
        if ground_truth is None:
            raise MissingGroundTruthError(
                "CoverageMetric requires ground_truth (the reference output). "
                "Provide a reference summary or key-point list for each evaluation case."
            )
        return await super().evaluate(prompt, input, output, ground_truth)

    # --- system prompts (packaged markdown resources) ---

    def claim_extraction_system_prompt(self) -> str:
        return load_completeness_resource("claim_extraction")

    def reference_extraction_system_prompt(self) -> str:
        return load_completeness_resource("reference_extraction")

    def verdict_system_prompt(self) -> str:
        return load_completeness_resource("verdict")

    def attribution_system_prompt(self) -> str:
        return load_completeness_resource("attribution")

    # --- user prompts ---

    def claim_extraction_prompt(self, output: str) -> str:
        return f"<output>\n{output}\n</output>"

    def reference_extraction_prompt(self, input: str, ground_truth: str | None) -> str:
        # Coverage uses ground_truth as the reference; input is ignored.
        return f"<reference>\n{ground_truth}\n</reference>"

    def verdict_prompt(self, claims: list[str], reference_points: list[str]) -> str:
        claims_text: str = "\n".join(f"- {c}" for c in claims) if claims else "(the output produced no factual claims)"
        refs_text: str = "\n".join(f"- {r}" for r in reference_points)
        return f"<reference_key_points>\n{refs_text}\n</reference_key_points>\n\n<output_claims>\n{claims_text}\n</output_claims>"

    # --- pipeline hook overrides ---

    def _should_run_verdicts(self, claims: list[str], reference_points: list[str]) -> bool:
        # Coverage iterates over reference points, so skip only when there is nothing to cover.
        # When reference points exist but output produces no claims, the LLM should emit all-fail
        # verdicts (one per reference point) — the prompt's "(no factual claims)" sentinel handles
        # this case without a separate code path.
        return bool(reference_points)

    def _build_failure_signal(
        self,
        verdict: ClaimVerdict,
        culprit_node_id: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> IssueSignal:
        # For coverage, `verdict.claim` holds a reference key point (from ground_truth), not an
        # output substring — so it cannot be used as `output_snippet` (the schema requires a
        # verbatim output quote). The missing key point goes into `rationale`; `output_snippet`
        # carries the truncated output as evidence of the gap.
        missing_point: str = verdict.claim
        verdict_reason: str = verdict.reason or "Reference key point was not covered by any output claim."
        rationale: str = f"Missing key point: {missing_point}. {verdict_reason}"
        # ground_truth is guaranteed non-None here — evaluate() raised MissingGroundTruthError otherwise.
        reference_text: str = ground_truth if ground_truth is not None else ""
        return IssueSignal(
            culprit_node_id=culprit_node_id,
            rationale=rationale,
            target_behavior="The output should cover every key point that appears in the reference.",
            success_criterion="Every reference key point is addressed by at least one output claim.",
            input_snippet=self._truncate(reference_text),
            output_snippet=self._truncate(output) if output.strip() else "(output produced no content)",
        )

    def _build_assessment(self, passing: list[ClaimVerdict], failing: list[ClaimVerdict]) -> str:
        total: int = len(passing) + len(failing)
        if total == 0:
            return "No reference key points extracted; nothing to cover."
        return f"{len(passing)}/{total} reference key points covered."


class CompletenessMetric(CoverageMetric):
    """Alias-style summarization completeness metric with user-facing naming."""

    name: ClassVar[str] = "completeness"
    description: ClassVar[str] = "Checks that the output covers key points from the ground_truth reference (summarization)."
