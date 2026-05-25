"""GEvalMetric — single-criterion configurable LLM judge."""

from __future__ import annotations

import hashlib
from typing import ClassVar

from ..._metrics.base_llm_judge import BaseLLMJudgeMetric, RenderPromptStrategy
from ...config import LiteLLMConfig


class GEvalMetric(BaseLLMJudgeMetric):
    """Configurable single-criterion judge.

    Instantiate once per criterion. For multiple criteria, use multiple instances.
    Each instance has a distinct `name` derived from a SHA-256 digest of the criteria string.

    Example::

        concise = GEvalMetric(config, criteria="The output must be concise (under 50 words).")
        accurate = GEvalMetric(config, criteria="The output must be factually accurate.")
    """

    description: ClassVar[str] = "Evaluates the output against a single custom criterion."
    # `name` is instance-level (derived from criteria) — see `__init__` below.
    name: ClassVar[str] = "g_eval"  # class-level default; overridden per-instance

    def __init__(
        self,
        litellm_config: LiteLLMConfig,
        criteria: str,
        render_strategy: RenderPromptStrategy | None = None,
    ) -> None:
        super().__init__(litellm_config, render_strategy)
        self.criteria: str = criteria
        # Instance-level name derived from criteria so multiple instances stay distinct.
        digest: str = hashlib.sha256(criteria.encode()).hexdigest()[:8]
        self.name: str = f"g_eval_{digest}"  # type: ignore[assignment]

    def build_system_prompt(self) -> str:
        return (
            "You are an impartial LLM judge evaluating a language model's output against a single criterion.\n\n"
            f"Criterion: {self.criteria}\n\n"
            "Given the prompt (with <!-- node-id --> markers), the input, and the output, "
            "judge whether the output satisfies the criterion. "
            "Return a MetricResult with:\n"
            "- score: 0.0 (criterion clearly violated) to 1.0 (criterion clearly satisfied)\n"
            "- assessment: concise narrative of your judgment\n"
            "- signals: one IssueSignal per violation found, each citing the culprit_node_id "
            "  from the <!-- id --> markers in the prompt\n"
            "- preserve: aspects of the prompt that are already working well"
        )
