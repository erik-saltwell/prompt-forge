from __future__ import annotations

from typing import ClassVar

from prompt_model._metrics.base_llm_judge import BaseLLMJudgeMetric, RenderPromptStrategy
from prompt_model.config import LiteLLMConfig


class GenericLLMJudgeMetric(BaseLLMJudgeMetric):
    """Configurable rubric-based judge.

    Provide a `rubric` string describing the evaluation criteria; the judge
    returns a `MetricResult` via structured output.
    """

    description: ClassVar[str] = "Evaluates the output against a provided rubric."
    name: ClassVar[str] = "generic_llm_judge"  # class-level default

    def __init__(
        self,
        name: str,
        description: str,
        rubric: str,
        judge_llm: LiteLLMConfig,
        render_strategy: RenderPromptStrategy | None = None,
    ) -> None:
        super().__init__(litellm_config=judge_llm, render_strategy=render_strategy)
        self.name: str = name  # type: ignore[assignment]
        self.description: str = description  # type: ignore[assignment]
        self.rubric: str = rubric

    def build_system_prompt(self) -> str:
        return (
            f"You are an impartial judge. Evaluate the output based on the following rubric:\n\n"
            f"{self.rubric}\n\n"
            "The prompt is shown with <!-- node-id --> markers. "
            "Return a MetricResult with a score (0.0–1.0), assessment, "
            "IssueSignals citing culprit node IDs, and preserve notes."
        )
