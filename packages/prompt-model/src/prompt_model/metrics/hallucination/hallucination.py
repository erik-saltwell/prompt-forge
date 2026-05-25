"""HallucinationMetric — general-purpose grounding check.

Checks whether the output contains facts not supported by the input (context).
Does not require ground_truth; uses `input` as the grounding source.
"""

from __future__ import annotations

from typing import ClassVar

from ..._metrics.base_llm_judge import BaseLLMJudgeMetric, RenderPromptStrategy
from ...config import LiteLLMConfig


class HallucinationMetric(BaseLLMJudgeMetric):
    """General-purpose hallucination detector.

    Verifies that every factual claim in the output is supported by the input context.
    `ground_truth` is accepted but not used as the primary context — `input` is.
    """

    name: ClassVar[str] = "hallucination"
    description: ClassVar[str] = "Detects facts in the output not grounded in the input context."

    def __init__(
        self,
        litellm_config: LiteLLMConfig,
        render_strategy: RenderPromptStrategy | None = None,
    ) -> None:
        super().__init__(litellm_config, render_strategy)

    def build_system_prompt(self) -> str:
        return (
            "You are a hallucination detection judge. "
            "Your job is to identify claims in the model output that are NOT supported by the provided context (input).\n\n"
            "The prompt is shown with <!-- node-id --> markers. When a prompt instruction causes the model "
            "to assert unsupported facts, cite the responsible node's id as culprit_node_id.\n\n"
            "Return a MetricResult with:\n"
            "- score: 1.0 if all claims are grounded, 0.0 if clear hallucinations are present, "
            "  fractional for partial grounding\n"
            "- assessment: concise narrative\n"
            "- signals: one IssueSignal per hallucinated claim\n"
            "- preserve: prompt instructions that are correctly constraining the model"
        )

    def build_user_prompt(
        self,
        rendered_prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> str:
        # input is the grounding context; ground_truth is secondary
        gt_block: str = f"\n\n<ground_truth>\n{ground_truth}\n</ground_truth>" if ground_truth is not None else ""
        return f"<prompt>\n{rendered_prompt}\n</prompt>\n\n<context>\n{input}\n</context>\n\n<output>\n{output}\n</output>{gt_block}"
