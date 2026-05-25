"""BaseClaimMetric — four-step claim-by-claim evaluation pipeline.

Steps:
  1. Extract claims from `output` (LLM call).
  2. Extract reference points from `input` or `ground_truth` (LLM call).
  3. For each claim, verdict: passes / fails + reason (LLM call).
  4. Batched node attribution: map each failing claim to a culprit_node_id (LLM call).

Score = fraction of passing verdicts.
Each failing verdict becomes one IssueSignal.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel, Field

from .._actor._critic_markdown import to_critic_markdown
from .._llm import acomplete
from .._prompt import parse_from_string
from ..config import LiteLLMConfig
from .result import IssueSignal, MetricResult


class ClaimVerdict(BaseModel):
    claim: str
    passes: bool
    reason: str | None = Field(default=None, description="Required when passes=False; why the claim fails.")


class _ClaimList(BaseModel):
    claims: list[str]


class _ReferenceList(BaseModel):
    reference_points: list[str]


class _VerdictList(BaseModel):
    verdicts: list[ClaimVerdict]


class NodeAttribution(BaseModel):
    claim: str
    culprit_node_id: str = Field(description="ID of the prompt node most responsible for this claim failing, or 'document'.")


class _AttributionList(BaseModel):
    attributions: list[NodeAttribution]


class BaseClaimMetric(ABC):
    """Abstract base for claim-by-claim evaluation metrics (alignment, coverage).

    Subclasses provide the three prompt-template methods. The base class owns the
    four-step pipeline, score computation, and `IssueSignal` assembly.
    """

    name: ClassVar[str]
    description: ClassVar[str]

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        self.litellm_config: LiteLLMConfig = litellm_config

    # --- subclass interface ---

    @abstractmethod
    def claim_extraction_prompt(self, output: str) -> str:
        """Prompt that asks the LLM to extract atomic claims from `output`."""

    @abstractmethod
    def reference_extraction_prompt(self, input: str, ground_truth: str | None) -> str:
        """Prompt that asks the LLM to extract trusted reference points."""

    @abstractmethod
    def verdict_prompt(self, claims: list[str], reference_points: list[str]) -> str:
        """Prompt that asks the LLM to verdict each claim against the reference points."""

    # --- system prompts (overridable; default to thin scaffolding shared by all claim metrics) ---

    def claim_extraction_system_prompt(self) -> str:
        """System prompt for the claim-extraction step. Override to supply metric-specific instructions."""
        return "Extract atomic factual claims from the text. Return a JSON object with a 'claims' list."

    def reference_extraction_system_prompt(self) -> str:
        """System prompt for the reference-extraction step. Override to supply metric-specific instructions."""
        return "Extract key reference points / trusted facts from the text. Return a JSON object with a 'reference_points' list."

    def verdict_system_prompt(self) -> str:
        """System prompt for the verdict step. Override to supply metric-specific instructions."""
        return "For each claim, determine if it is supported by the reference points. Return a JSON object with a 'verdicts' list."

    def attribution_system_prompt(self) -> str:
        """System prompt for the attribution step. Override to supply metric-specific instructions."""
        return (
            "You are a prompt attribution judge. Given a prompt with <!-- id --> node markers "
            "and a list of claims that failed evaluation, identify which prompt node is most "
            "responsible for each failure. Use 'document' when no specific node is culpable."
        )

    # --- pipeline steps (overridable for testing) ---

    async def _extract_claims(self, output: str) -> list[str]:
        result: _ClaimList = await acomplete(
            system_prompt=self.claim_extraction_system_prompt(),
            user_prompt=self.claim_extraction_prompt(output),
            config=self.litellm_config,
            response_format=_ClaimList,
            log_name=f"{self.name}:claims",
        )
        return result.claims

    async def _extract_reference_points(self, input: str, ground_truth: str | None) -> list[str]:
        result: _ReferenceList = await acomplete(
            system_prompt=self.reference_extraction_system_prompt(),
            user_prompt=self.reference_extraction_prompt(input, ground_truth),
            config=self.litellm_config,
            response_format=_ReferenceList,
            log_name=f"{self.name}:references",
        )
        return result.reference_points

    def _should_run_verdicts(self, claims: list[str], reference_points: list[str]) -> bool:
        """Whether the verdict LLM call should fire for this (claims, reference_points) pair.

        Default skips when there are no output claims (alignment-style: nothing to judge).
        Coverage-style metrics iterating over reference points should override to skip on
        empty reference_points instead, and synthesize all-fail verdicts when reference
        points exist but no output claims do.
        """
        return bool(claims)

    async def _generate_verdicts(self, claims: list[str], reference_points: list[str]) -> list[ClaimVerdict]:
        if not self._should_run_verdicts(claims, reference_points):
            return []
        result: _VerdictList = await acomplete(
            system_prompt=self.verdict_system_prompt(),
            user_prompt=self.verdict_prompt(claims, reference_points),
            config=self.litellm_config,
            response_format=_VerdictList,
            log_name=f"{self.name}:verdicts",
        )
        return result.verdicts

    async def _attribute_nodes(self, failing_verdicts: list[ClaimVerdict], prompt_with_ids: str) -> list[NodeAttribution]:
        if not failing_verdicts:
            return []
        claims_text: str = "\n".join(f"- {v.claim}: {v.reason}" for v in failing_verdicts)
        user_prompt: str = f"<prompt>\n{prompt_with_ids}\n</prompt>\n\n<failing_claims>\n{claims_text}\n</failing_claims>"
        result: _AttributionList = await acomplete(
            system_prompt=self.attribution_system_prompt(),
            user_prompt=user_prompt,
            config=self.litellm_config,
            response_format=_AttributionList,
            log_name=f"{self.name}:attribution",
        )
        return result.attributions

    # --- signal and assessment construction (overridable) ---

    def _build_failure_signal(
        self,
        verdict: ClaimVerdict,
        culprit_node_id: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> IssueSignal:
        """Construct an IssueSignal for one failing verdict. Override to customize per-metric framing.

        Default values are tuned for claim-iteration metrics (alignment-style): each verdict
        represents one output claim, so `output_snippet=verdict.claim` is a verbatim output quote.
        Coverage-style metrics whose `verdict.claim` holds a reference key point (not an output
        substring) must override this to satisfy the IssueSignal schema.
        """
        return IssueSignal(
            culprit_node_id=culprit_node_id,
            rationale=verdict.reason or "Claim did not pass verification.",
            target_behavior="The output should only assert claims supported by the source.",
            success_criterion="All claims in the output are verifiable against the reference.",
            input_snippet=self._truncate(input),
            output_snippet=verdict.claim,
        )

    @staticmethod
    def _truncate(text: str, limit: int = 200) -> str:
        """Truncate `text` to at most `limit` characters, appending an ellipsis when shortened."""
        return text if len(text) <= limit else text[:limit] + "…"

    def _build_assessment(self, passing: list[ClaimVerdict], failing: list[ClaimVerdict]) -> str:
        """Narrative summary line for the MetricResult. Override to use metric-specific vocabulary."""
        total: int = len(passing) + len(failing)
        if total == 0:
            return "No claims extracted from output."
        return f"{len(passing)}/{total} claims passed."

    # --- public evaluate ---

    async def evaluate(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> MetricResult:
        claims, reference_points = await self._extract_claims(output), await self._extract_reference_points(input, ground_truth)
        verdicts: list[ClaimVerdict] = await self._generate_verdicts(claims, reference_points)

        passing: list[ClaimVerdict] = [v for v in verdicts if v.passes]
        failing: list[ClaimVerdict] = [v for v in verdicts if not v.passes]

        score: float = len(passing) / len(verdicts) if verdicts else 1.0

        document = parse_from_string(prompt)
        prompt_with_ids: str = to_critic_markdown(document)
        attributions: list[NodeAttribution] = await self._attribute_nodes(failing, prompt_with_ids)
        attribution_map: dict[str, str] = {a.claim: a.culprit_node_id for a in attributions}

        signals: list[IssueSignal] = [
            self._build_failure_signal(v, attribution_map.get(v.claim, "document"), input, output, ground_truth) for v in failing
        ]

        return MetricResult(
            metric_name=self.name,
            score=score,
            assessment=self._build_assessment(passing, failing),
            signals=signals,
        )
