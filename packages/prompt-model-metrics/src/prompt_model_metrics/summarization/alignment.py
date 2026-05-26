"""AlignmentMetric — summarization faithfulness via claim-by-claim verification.

Checks whether claims in the output align with facts in the input (source text).
Tuned and validated for summarization tasks.
Reference source: `input` (the source document).
"""

from __future__ import annotations

from typing import ClassVar

from prompt_model._metrics.base_claim_metric import BaseClaimMetric
from prompt_model.config import LiteLLMConfig

from ._alignment_resources import load_alignment_resource


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

    # --- system prompts (packaged markdown resources) ---

    def claim_extraction_system_prompt(self) -> str:
        return load_alignment_resource("claim_extraction")

    def reference_extraction_system_prompt(self) -> str:
        return load_alignment_resource("reference_extraction")

    def verdict_system_prompt(self) -> str:
        return load_alignment_resource("verdict")

    def attribution_system_prompt(self) -> str:
        return load_alignment_resource("attribution")

    # --- user prompts ---

    def claim_extraction_prompt(self, output: str) -> str:
        return f"<summary>\n{output}\n</summary>"

    def reference_extraction_prompt(self, input: str, ground_truth: str | None) -> str:
        # Alignment uses input as the source of truth; ground_truth is ignored.
        return f"<source>\n{input}\n</source>"

    def verdict_prompt(self, claims: list[str], reference_points: list[str]) -> str:
        claims_text: str = "\n".join(f"- {c}" for c in claims)
        refs_text: str = "\n".join(f"- {r}" for r in reference_points)
        return f"<source_facts>\n{refs_text}\n</source_facts>\n\n<summary_claims>\n{claims_text}\n</summary_claims>"
