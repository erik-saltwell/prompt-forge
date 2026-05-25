"""AlignmentMetric — summarization faithfulness via claim-by-claim verification.

Checks whether claims in the output align with facts in the input (source text).
Tuned and validated for summarization tasks.
Reference source: `input` (the source document).
"""

from __future__ import annotations

from typing import ClassVar

from ..._metrics.base_claim_metric import BaseClaimMetric
from ...config import LiteLLMConfig


class AlignmentMetric(BaseClaimMetric):
    """Checks that the output's claims are faithful to the input source text.

    Each claim in the output is checked against facts extracted from `input`.
    Failing claims become `IssueSignal`s attributed to the prompt node most
    likely responsible for causing the misalignment.

    Designed for summarization. Does not require `ground_truth`.
    """

    name: ClassVar[str] = "alignment"
    description: ClassVar[str] = "Checks that output claims are faithful to the input source text (summarization)."

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        super().__init__(litellm_config)

    def claim_extraction_prompt(self, output: str) -> str:
        return (
            f"Extract every atomic factual claim made in the following summary. "
            f"Each claim should be a single, verifiable statement.\n\n"
            f"Summary:\n{output}"
        )

    def reference_extraction_prompt(self, input: str, ground_truth: str | None) -> str:
        # Alignment uses input as the source of truth; ground_truth is ignored.
        return (
            f"Extract the key facts stated in the following source text. "
            f"Each fact should be a single, verifiable statement.\n\n"
            f"Source text:\n{input}"
        )

    def verdict_prompt(self, claims: list[str], reference_points: list[str]) -> str:
        claims_text: str = "\n".join(f"- {c}" for c in claims)
        refs_text: str = "\n".join(f"- {r}" for r in reference_points)
        return (
            f"For each summary claim, determine whether it is directly supported by the source facts. "
            f"A claim PASSES if it is consistent with (or neutral with respect to) the source facts. "
            f"A claim FAILS if it contradicts a source fact.\n\n"
            f"Source facts:\n{refs_text}\n\n"
            f"Summary claims:\n{claims_text}"
        )
