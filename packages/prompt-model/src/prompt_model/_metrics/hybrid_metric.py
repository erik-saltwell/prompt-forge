"""Hybrid metric base class: deterministic score + LLM-generated `IssueSignal`.

Subclasses provide pure-compute scoring via `score_case` and optionally pass a
`LiteLLMConfig` for the judge. On a miss (or whenever `needs_judge` returns
True), the base class renders the prompt with an HTML-comment ID overlay,
calls the judge LLM with a `JudgeDiagnosis` response schema, and assembles a
fully-built `IssueSignal` — with verbatim `input_snippet` and `output_snippet`
the metric supplies (the LLM never paraphrases evidence).

The default judge system prompt lives at `_resources/hybrid_judge.md`.
Subclasses customise via either:

- `judge_system_prompt_resource: ClassVar[str] = "my_judge"` — point at a
  different bundled `.md` file.
- `def judge_system_prompt(self) -> str: ...` — override for runtime
  templating.

Both are honoured; the method wins when both are present.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel, Field, field_validator

from .._actor._critic_markdown import to_critic_markdown
from .._llm import acomplete
from .._prompt import parse_from_string
from ..config import LiteLLMConfig
from ._resources import load_metric_resource
from .result import IssueSignal, MetricResult


class JudgeDiagnosis(BaseModel):
    """Structured response the hybrid judge returns for one failed case."""

    culprit_node_id: str = Field(
        description=(
            "ID of the prompt node most responsible for the failure. Must be an id that appears "
            "in an <!-- id --> comment in the prompt, or the literal string 'document' when the "
            "failure cannot be localized to a single node."
        ),
    )
    rationale: str = Field(description="Why the cited node is at fault for this specific failure.")
    target_behavior: str = Field(description="What the prompt should make the target LLM do after the fix.")
    success_criterion: str = Field(description="Observable predicate that confirms the fix worked.")
    suggested_prompt_change: str | None = Field(
        default=None,
        description="Optional concrete edit. Null when the judge can identify the fault but isn't confident in a specific fix.",
    )

    @field_validator("suggested_prompt_change", mode="before")
    @classmethod
    def _coerce_to_string(cls, value: object) -> object:
        if value is None or isinstance(value, str):
            return value
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        return str(value)


class HybridMetric(ABC):
    """Deterministic score + optional LLM-generated `IssueSignal`s.

    Subclass surface:

    - `name`, `description` ClassVars (required).
    - `score_case(prompt, input, output, ground_truth) -> (score, assessment)` — the only
      abstract method. Pure compute, no I/O. `score` is in `[0, 1]`, higher is better.
    - `needs_judge(score) -> bool` — override to change when the judge fires. Default: `score < 1.0`.
    - `judge_system_prompt_resource: ClassVar[str]` — bundled `.md` filename (default `"hybrid_judge"`).
    - `judge_system_prompt(self) -> str` — override for runtime templating; falls back to the resource.
    - `judge_user_prompt(...)` — override to customise the user message shape.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    judge_system_prompt_resource: ClassVar[str] = "hybrid_judge"

    def __init__(self, judge_llm: LiteLLMConfig | None = None) -> None:
        self.judge_llm: LiteLLMConfig | None = judge_llm

    @abstractmethod
    def score_case(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> tuple[float, str]:
        """Return `(score, assessment)`. Score in `[0, 1]`; assessment narrates the judgment."""

    def needs_judge(self, score: float) -> bool:
        """Whether to call the LLM judge for this score. Default: anything less than perfect."""
        return score < 1.0

    def judge_system_prompt(self) -> str:
        """Return the system prompt the judge sees. Default: load the bundled resource."""
        return load_metric_resource(self.judge_system_prompt_resource)

    def judge_user_prompt(
        self,
        prompt_with_ids: str,
        case_input: str,
        model_output: str,
        ground_truth: str | None,
        assessment: str,
    ) -> str:
        """Return the user message the judge sees. Default: the four-block layout from `hybrid_judge.md`."""
        gt_block: str = f"\n\n<ground_truth>\n{ground_truth}\n</ground_truth>" if ground_truth is not None else ""
        return (
            f"<prompt>\n{prompt_with_ids}\n</prompt>\n\n"
            f"<case_input>\n{case_input}\n</case_input>\n\n"
            f"<model_output>\n{model_output}\n</model_output>"
            f"{gt_block}\n\n"
            f"<assessment>\n{assessment}\n</assessment>"
        )

    async def evaluate(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> MetricResult:
        score: float
        assessment: str
        score, assessment = self.score_case(prompt, input, output, ground_truth)
        signals: list[IssueSignal] = []
        if self.needs_judge(score) and self.judge_llm is not None:
            signals = [await self._run_judge(prompt, input, output, ground_truth, assessment)]
        return MetricResult(metric_name=self.name, score=score, assessment=assessment, signals=signals)

    async def _run_judge(
        self,
        prompt: str,
        case_input: str,
        model_output: str,
        ground_truth: str | None,
        assessment: str,
    ) -> IssueSignal:
        document = parse_from_string(prompt)
        prompt_with_ids: str = to_critic_markdown(document)
        diagnosis: JudgeDiagnosis = await acomplete(
            system_prompt=self.judge_system_prompt(),
            user_prompt=self.judge_user_prompt(prompt_with_ids, case_input, model_output, ground_truth, assessment),
            config=_require(self.judge_llm),
            response_format=JudgeDiagnosis,
            log_name=self.name,
        )
        return IssueSignal(
            culprit_node_id=diagnosis.culprit_node_id or "document",
            rationale=diagnosis.rationale,
            target_behavior=diagnosis.target_behavior,
            success_criterion=diagnosis.success_criterion,
            suggested_prompt_change=diagnosis.suggested_prompt_change,
            input_snippet=_truncate(case_input),
            output_snippet=_truncate(model_output) or "(empty)",
        )


def _require(cfg: LiteLLMConfig | None) -> LiteLLMConfig:
    if cfg is None:
        raise RuntimeError("HybridMetric._run_judge called without a configured judge_llm")
    return cfg


def _truncate(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
