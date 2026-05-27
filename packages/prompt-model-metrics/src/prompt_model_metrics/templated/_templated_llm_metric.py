from __future__ import annotations

import hashlib
from typing import Any, ClassVar

import litellm
from prompt_model import IssueSignal, MetricResult
from prompt_model._llm._concurrency import get_llm_semaphore
from prompt_model._llm.call import _set_response_format  # noqa: PLC2701  reusing schema-build logic
from prompt_model._metrics.protocol import MissingGroundTruthError
from prompt_model._prompt import parse_from_string
from prompt_model.config import LiteLLMConfig
from prompt_model.strategies.prompt_rendering_strategy import MarkdownRenderPromptStrategy, RenderPromptStrategy
from pydantic import BaseModel, Field

from ._logprob_scoring import LOGPROBS_COUNT, extract_weighted_score
from ._prompt_context import SCORE_MAX, SCORE_MIN, PromptContext
from ._resources import render_template


class _JudgeResponse(BaseModel):
    """Judge LLM response. Field order matters: `score` must be first for logprob extraction."""

    score: int = Field(ge=SCORE_MIN, le=SCORE_MAX, description="Integer score in [1,5].")
    assessment: str = Field(description="Concise narrative explaining the score.")
    signal: IssueSignal | None = Field(default=None, description="Single issue signal if criterion failed, else null.")
    preserve: list[str] = Field(default_factory=list, description="Aspects of the prompt that work and should not be broken.")


class TemplatedLLMMetric:
    """Single-criterion LLM-judge metric driven by a pre-built `PromptContext`.

    The metric is criterion-agnostic at the type level — every per-criterion concern
    (evaluation steps, scoring rubric, ground-truth requirement, optional definitions and
    reminders) lives in `PromptContext`. Build the context with one of the factory
    functions in `_factories.py` (`prompt_context_from_llm`, `prompt_context_from_yaml`,
    `prompt_context_from_json`).

    Each instance has a distinct `name` derived from the SHA-256 digest of the context's
    criterion string.
    """

    description: ClassVar[str] = "Evaluates the output against a single custom criterion."
    name: ClassVar[str] = "templated_llm"  # overridden per-instance in __init__

    def __init__(
        self,
        context: PromptContext,
        judge_llm_config: LiteLLMConfig,
        render_strategy: RenderPromptStrategy | None = None,
    ) -> None:
        self.context: PromptContext = context
        self.judge_llm_config: LiteLLMConfig = judge_llm_config
        self.render_strategy: RenderPromptStrategy = render_strategy if render_strategy is not None else MarkdownRenderPromptStrategy()
        digest: str = hashlib.sha256(context.criterion.encode()).hexdigest()[:8]
        self.name: str = f"templated_llm_{digest}"  # type: ignore[assignment]

    async def evaluate(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> MetricResult:
        # Step 1: validate inputs. `evaluate` is the single validation site — the public
        # `build_system_prompt` / `build_user_prompt` helpers trust their callers.
        self._validate_required_texts(prompt=prompt, input=input, output=output)
        context: PromptContext = self.context
        self._validate_ground_truth(context, ground_truth)

        # Step 2: render the two prompts the judge sees.
        system_prompt: str = self.build_system_prompt(ground_truth)
        user_prompt: str = self.build_user_prompt(prompt, input, output, ground_truth)

        # Step 3: call the judge LLM. We use the raw litellm response (not the helper
        # `acomplete`) because the next step needs top-token logprobs at the score position,
        # which the helper discards. `_call_judge` returns both the parsed response and the
        # raw response so the scoring step can read logprobs off the raw object.
        judge_response: _JudgeResponse
        raw_response: Any
        judge_response, raw_response = await _call_judge(self.judge_llm_config, system_prompt, user_prompt)

        # Step 4: compute the score. Prefer the logprob-weighted expectation Σ P(t)·int(t) over
        # the score-token position — this turns a discrete 1-5 sample into a continuous estimate
        # that reflects the judge's confidence. Fall back to the integer score if logprobs are
        # unavailable. Then normalise from the rubric's 1-5 range to MetricResult's [0,1].
        weighted: float | None = extract_weighted_score(raw_response)
        effective_score: float = weighted if weighted is not None else float(judge_response.score)
        normalized: float = context.normalize_score(effective_score)

        # Step 5: package the result. The judge emits at most one IssueSignal per call (single
        # criterion → single failure mode); wrap it in the list MetricResult expects.
        signals: list[IssueSignal] = [judge_response.signal] if judge_response.signal is not None else []
        return MetricResult(
            metric_name=self.name,
            score=normalized,
            assessment=judge_response.assessment,
            signals=signals,
            preserve=judge_response.preserve,
        )

    def build_system_prompt(self, ground_truth: str | None) -> str:
        """Render the judge system prompt from the metric context.

        Does not validate inputs — `evaluate` is the single validation site. Direct callers
        should pre-validate if they want the same guarantees `evaluate` provides.
        """
        context: PromptContext = self.context
        return render_template(
            "system_prompt",
            criterion=context.criterion,
            definitions=context.definitions,
            evaluation_steps=context.evaluation_steps,
            evaluation_rubric=context.scoring_rubric,
            requires_ground_truth=context.requires_ground_truth,
            important_reminders=context.important_reminders,
            expected_output=ground_truth if ground_truth is not None else "",
            prompt_format=self.render_strategy.describe_format(),
            score_min=SCORE_MIN,
            score_max=SCORE_MAX,
        )

    def build_user_prompt(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> str:
        """Render the judge user prompt for one evaluated prompt/case/output tuple.

        Does not validate inputs — `evaluate` is the single validation site.
        """
        document = parse_from_string(prompt)
        rendered_prompt: str = self.render_strategy.render(document, focus_ids=None)
        return render_template(
            "user_prompt",
            prompt_text=rendered_prompt,
            actual_input=input,
            actual_output=output,
            expected_output=ground_truth if ground_truth is not None else "",
        )

    @staticmethod
    def _validate_required_texts(prompt: str | None, input: str | None, output: str | None) -> None:
        for field_name, value in (("prompt", prompt), ("input", input), ("output", output)):
            if value is None or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string.")

    def _validate_ground_truth(self, context: PromptContext, ground_truth: str | None) -> None:
        if context.requires_ground_truth and (ground_truth is None or not ground_truth.strip()):
            raise MissingGroundTruthError(f"Metric {self.name!r} requires ground_truth for criterion: {context.criterion!r}")


async def _call_judge(
    judge_llm_config: LiteLLMConfig,
    system_prompt: str,
    user_prompt: str,
) -> tuple[_JudgeResponse, Any]:
    """Call the judge LLM with structured output AND token logprobs requested.

    We bypass `prompt_model.helpers.acomplete` because it discards the raw response —
    the caller needs to read `top_logprobs` at the score-token position to compute a
    confidence-weighted score. Returns `(parsed_response, raw_litellm_response)`.
    """
    kwargs: dict[str, Any] = judge_llm_config.to_completion_kwargs()
    _set_response_format(kwargs, _JudgeResponse)
    kwargs["temperature"] = 1.0
    kwargs["logprobs"] = True
    kwargs["top_logprobs"] = LOGPROBS_COUNT
    async with get_llm_semaphore():
        raw_response: Any = await litellm.acompletion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **kwargs,
        )
    content: str = raw_response.choices[0].message.content
    if not isinstance(content, str):
        raise ValueError(f"Judge response content is not a string: {type(content).__name__}")
    parsed: _JudgeResponse = _JudgeResponse.model_validate_json(content)
    return parsed, raw_response
