"""CoverageMetric — summarization completeness via claim-by-claim verification.

Checks whether the output covers the key points from the ground_truth reference.
Tuned and validated for summarization tasks.
Reference source: `ground_truth` (the reference summary or key-point list).
"""

from __future__ import annotations

from typing import ClassVar

from ..._metrics.base_claim_metric import BaseClaimMetric
from ..._metrics.protocol import MissingGroundTruthError
from ..._metrics.result import MetricResult
from ...config import LiteLLMConfig


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

    def claim_extraction_prompt(self, output: str) -> str:
        return (
            f"Extract every atomic factual claim made in the following output. "
            f"Each claim should be a single, verifiable statement.\n\n"
            f"Output:\n{output}"
        )

    def reference_extraction_prompt(self, input: str, ground_truth: str | None) -> str:
        # Coverage uses ground_truth as the reference; input is secondary.
        return (
            f"Extract the key points that should be covered in a good summary of this content. "
            f"Each key point should be a single, verifiable statement.\n\n"
            f"Reference:\n{ground_truth}"
        )

    def verdict_prompt(self, claims: list[str], reference_points: list[str]) -> str:
        claims_text: str = "\n".join(f"- {c}" for c in claims)
        refs_text: str = "\n".join(f"- {r}" for r in reference_points)
        return (
            f"For each reference key point, determine whether it is covered by the output claims. "
            f"A key point PASSES if at least one output claim addresses it. "
            f"A key point FAILS if it is absent or only partially addressed.\n\n"
            f"Output claims:\n{claims_text}\n\n"
            f"Reference key points:\n{refs_text}"
        )
