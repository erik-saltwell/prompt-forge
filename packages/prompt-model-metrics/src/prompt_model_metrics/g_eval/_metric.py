from __future__ import annotations

import hashlib
import logging
import math
from typing import Any, ClassVar, cast

import litellm
from prompt_model import IssueSignal, MetricResult
from prompt_model._llm._concurrency import get_llm_semaphore
from prompt_model._llm.call import _set_response_format  # noqa: PLC2701  reusing schema-build logic
from prompt_model._metrics.protocol import MissingGroundTruthError
from prompt_model._prompt import parse_from_string
from prompt_model.config import LiteLLMConfig
from prompt_model.strategies.prompt_rendering_strategy import MarkdownRenderPromptStrategy, RenderPromptStrategy
from pydantic import BaseModel, Field

from ._ai_prompt_factory import create_prompt_context
from ._prompt_context import SCORE_MAX, SCORE_MIN, PromptContext
from ._resources import render_template

_logger: logging.Logger = logging.getLogger(__name__)

_SCORE_TOKENS: frozenset[str] = frozenset({"1", "2", "3", "4", "5"})
_NUMERIC_MASS_WARN_THRESHOLD: float = 0.9
_TOP_LOGPROBS: int = 5


class _JudgeResponse(BaseModel):
    """Judge LLM response. Field order matters: `score` must be first for logprob extraction."""

    score: int = Field(ge=SCORE_MIN, le=SCORE_MAX, description="Integer score in [1,5].")
    assessment: str = Field(description="Concise narrative explaining the score.")
    signal: IssueSignal | None = Field(default=None, description="Single issue signal if criterion failed, else null.")
    preserve: list[str] = Field(default_factory=list, description="Aspects of the prompt that work and should not be broken.")


class GEvalMetric:
    """Single-criterion LLM-judge metric with optional logprob-weighted scoring.

    Instantiate once per criterion. Each instance has a distinct `name` derived from the
    SHA-256 digest of the criterion string. `PromptContext` is built lazily on first
    `evaluate` via the module-level factory cache.
    """

    description: ClassVar[str] = "Evaluates the output against a single custom criterion (G-Eval)."
    name: ClassVar[str] = "g_eval"  # overridden per-instance in __init__

    def __init__(
        self,
        judge_llm_config: LiteLLMConfig,
        factory_llm_config: LiteLLMConfig,
        criterion: str,
        render_strategy: RenderPromptStrategy | None = None,
    ) -> None:
        self.judge_llm_config: LiteLLMConfig = judge_llm_config
        self.factory_llm_config: LiteLLMConfig = factory_llm_config
        self.criterion: str = criterion
        self.render_strategy: RenderPromptStrategy = render_strategy if render_strategy is not None else MarkdownRenderPromptStrategy()
        digest: str = hashlib.sha256(criterion.encode()).hexdigest()[:8]
        self.name: str = f"g_eval_{digest}"  # type: ignore[assignment]

    async def evaluate(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> MetricResult:
        context: PromptContext = await create_prompt_context(self.criterion, self.factory_llm_config)

        if context.requires_ground_truth and ground_truth is None:
            raise MissingGroundTruthError(f"Metric {self.name!r} requires ground_truth for criterion: {self.criterion!r}")

        document = parse_from_string(prompt)
        rendered_prompt: str = self.render_strategy.render(document, focus_ids=None)

        system_prompt: str = "You are an impartial LLM judge. Follow the evaluation steps to produce a score per the rubric."
        user_prompt: str = render_template(
            "user_prompt",
            criterion=context.criterion,
            evaluation_steps=context.evaluation_steps,
            scoring_rubric=context.scoring_rubric,
            requires_ground_truth=context.requires_ground_truth,
            rendered_prompt=rendered_prompt,
            input=input,
            output=output,
            ground_truth=ground_truth if ground_truth is not None else "",
            score_min=SCORE_MIN,
            score_max=SCORE_MAX,
        )

        raw_response: Any = await _call_judge(system_prompt, user_prompt, self.judge_llm_config)
        content: str = raw_response.choices[0].message.content
        if not isinstance(content, str):
            raise ValueError(f"Judge response content is not a string: {type(content).__name__}")
        parsed: _JudgeResponse = _JudgeResponse.model_validate_json(content)

        weighted: float | None = _extract_weighted_score(raw_response)
        final_score_int: float = weighted if weighted is not None else float(parsed.score)
        normalized: float = context.normalize_score(final_score_int)

        signals: list[IssueSignal] = [parsed.signal] if parsed.signal is not None else []
        return MetricResult(
            metric_name=self.name,
            score=normalized,
            assessment=parsed.assessment,
            signals=signals,
            preserve=parsed.preserve,
        )


async def _call_judge(system_prompt: str, user_prompt: str, config: LiteLLMConfig) -> Any:
    """Call the judge LLM with structured output AND token logprobs requested.

    We bypass `prompt_model.helpers.acomplete` because it discards the raw response —
    we need to read `top_logprobs` at the score-token position.
    """
    kwargs: dict[str, Any] = config.to_completion_kwargs()
    _set_response_format(kwargs, _JudgeResponse)
    kwargs["temperature"] = 1.0
    kwargs["logprobs"] = True
    kwargs["top_logprobs"] = _TOP_LOGPROBS
    async with get_llm_semaphore():
        return await litellm.acompletion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **kwargs,
        )


def _extract_weighted_score(response: Any) -> float | None:
    """Compute Σ_i P(token_i) * int(token_i) over the score-token position.

    Returns `None` if the provider did not return logprobs, the score token cannot be
    located, or no numeric mass is present. Renormalises across {"1".."5"}; logs a
    warning if <90% of mass falls on numeric tokens.
    """
    try:
        choice: Any = response.choices[0]
        logprobs_obj: Any = getattr(choice, "logprobs", None)
        if logprobs_obj is None:
            return None
        content: Any = getattr(logprobs_obj, "content", None)
        if not content:
            return None
    except (AttributeError, IndexError, TypeError):
        return None

    score_position: Any = _find_score_token_position(content)
    if score_position is None:
        return None

    top: Any = getattr(score_position, "top_logprobs", None)
    if not top:
        return None

    numeric_mass: float = 0.0
    total_mass: float = 0.0
    weighted_sum: float = 0.0
    for entry in top:
        token: str = _strip_token(_attr(entry, "token"))
        logp: float | None = _attr(entry, "logprob")
        if logp is None:
            continue
        p: float = math.exp(logp)
        total_mass += p
        if token in _SCORE_TOKENS:
            numeric_mass += p
            weighted_sum += p * float(token)

    if numeric_mass <= 0.0:
        return None
    if total_mass > 0.0 and (numeric_mass / total_mass) < _NUMERIC_MASS_WARN_THRESHOLD:
        _logger.warning(
            "G-Eval: only %.1f%% of top-%d probability mass at score token is numeric (1-5).",
            100.0 * numeric_mass / total_mass,
            _TOP_LOGPROBS,
        )
    return weighted_sum / numeric_mass


def _find_score_token_position(content: list[Any]) -> Any:
    """Locate the token whose stripped form is one of '1'..'5' after the `"score"` field.

    JSON structured output emits roughly:  {"score": 4, "assessment": "...", ...
    We scan for the first 1-digit token in `{"1".."5"}` after we have seen `score`.
    """
    seen_score_key: bool = False
    for entry in content:
        raw: str = _attr(entry, "token") or ""
        stripped: str = _strip_token(raw)
        lowered: str = stripped.lower()
        if not seen_score_key:
            if "score" in lowered:
                seen_score_key = True
            continue
        if stripped in _SCORE_TOKENS:
            return entry
    return None


def _attr(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return cast(dict[str, Any], obj).get(name)
    return getattr(obj, name, None)


def _strip_token(token: str | None) -> str:
    if not token:
        return ""
    # Tokenizers may prefix with a leading space (e.g. " 4"). Strip whitespace + quotes.
    return token.strip().strip('"').strip("'")
