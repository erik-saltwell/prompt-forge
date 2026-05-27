"""Evaluation metrics for the g_eval context_factory prompt.

The prompt under optimization is a system prompt that, given a criterion as the
user turn, must emit a JSON object matching `PromptContextDraft`:

    {
      "reasoning": "...",
      "evaluation_steps": ["...", "..."],
      "scoring_rubric": [{"score_range": [1, 2], "expected_outcome": "..."}, ...],
      "requires_ground_truth": true | false
    }

Six metrics — five deterministic (HybridMetric: pure-compute score plus an LLM
judge that fires on a miss to localize the culprit node), and one LLM-judge
metric for semantic coherence between steps and rubric:

  1. JsonParseableMetric           — output parses as the expected schema
  2. RubricCoversRangeMetric       — bands tile [1, 5] with no gaps or overlaps
  3. StepsWellFormedMetric         — ≥1 step; each step is one focused operation
  4. ReasoningNonTrivialMetric     — reasoning has substance, not just an echo
  5. RequiresGroundTruthCorrectMetric — predicted bool matches the hand-labeled one
  6. RubricAndStepsCoherentMetric  — semantic alignment between steps and rubric
"""

from __future__ import annotations

import json
import re
from typing import Any, ClassVar, cast

from prompt_model import BaseLLMJudgeMetric, HybridMetric, Metric
from prompt_model.config import LiteLLMConfig

__all__ = [
    "JsonParseableMetric",
    "RubricAndStepsCoherentMetric",
    "RubricCoversRangeMetric",
    "ReasoningNonTrivialMetric",
    "RequiresGroundTruthCorrectMetric",
    "StepsWellFormedMetric",
    "build_g_eval_factory_metrics",
]

_SCORE_MIN: int = 1
_SCORE_MAX: int = 5

_FENCE_RE: re.Pattern[str] = re.compile(r"^```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _parse_output(output: str) -> dict[str, Any] | None:
    """Lenient JSON parse: strips surrounding code fences and finds the first balanced object."""
    stripped: str = _FENCE_RE.sub("", output.strip()).strip()
    try:
        parsed: object = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        start: int = stripped.find("{")
        end: int = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(stripped[start : end + 1])
        except (json.JSONDecodeError, ValueError):
            return None
    if isinstance(parsed, dict):
        return cast(dict[str, Any], parsed)
    return None


def _coerce_band(band: object) -> tuple[int, int] | None:
    """Extract (minimum, maximum) from a band dict's `score_range` field."""
    if not isinstance(band, dict):
        return None
    band_d: dict[str, Any] = cast(dict[str, Any], band)
    rng: object = band_d.get("score_range")
    if isinstance(rng, list | tuple) and len(rng) == 2:
        lo, hi = rng
        if isinstance(lo, int | float) and isinstance(hi, int | float):
            return int(lo), int(hi)
    if isinstance(rng, dict):
        rng_d: dict[str, Any] = cast(dict[str, Any], rng)
        lo = rng_d.get("minimum")
        hi = rng_d.get("maximum")
        if isinstance(lo, int | float) and isinstance(hi, int | float):
            return int(lo), int(hi)
    return None


# ---------------------------------------------------------------------------
# 1. JsonParseableMetric
# ---------------------------------------------------------------------------


class JsonParseableMetric(HybridMetric):
    """Output must parse as a JSON object with the four expected top-level keys."""

    name: ClassVar[str] = "json_parseable"
    description: ClassVar[str] = (
        "Checks the factory output is a JSON object with reasoning, evaluation_steps, scoring_rubric, and requires_ground_truth."
    )

    _REQUIRED_KEYS: ClassVar[frozenset[str]] = frozenset({"reasoning", "evaluation_steps", "scoring_rubric", "requires_ground_truth"})

    def __init__(self, judge_llm: LiteLLMConfig | None = None) -> None:
        super().__init__(judge_llm)

    def score_case(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> tuple[float, str]:
        parsed: dict[str, Any] | None = _parse_output(output)
        if parsed is None:
            return 0.0, "Output is not valid JSON (even with code-fence stripping)."
        missing: frozenset[str] = self._REQUIRED_KEYS - parsed.keys()
        if missing:
            return 0.0, f"Output JSON is missing required keys: {sorted(missing)}."
        return 1.0, "Output is a JSON object with all four required keys."


# ---------------------------------------------------------------------------
# 2. RubricCoversRangeMetric
# ---------------------------------------------------------------------------


class RubricCoversRangeMetric(HybridMetric):
    """`scoring_rubric` bands must collectively cover [1, 5] with no gaps or overlaps."""

    name: ClassVar[str] = "rubric_covers_range"
    description: ClassVar[str] = "Checks the scoring rubric bands tile the 1–5 integer range with no gaps or overlaps."

    def __init__(self, judge_llm: LiteLLMConfig | None = None) -> None:
        super().__init__(judge_llm)

    def score_case(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> tuple[float, str]:
        parsed: dict[str, Any] | None = _parse_output(output)
        if parsed is None:
            return 0.0, "Output is not parseable JSON; cannot evaluate rubric."
        rubric: object = parsed.get("scoring_rubric")
        if not isinstance(rubric, list) or not rubric:
            return 0.0, "scoring_rubric is missing or empty."

        bands: list[tuple[int, int]] = []
        for i, raw in enumerate(rubric):
            band: tuple[int, int] | None = _coerce_band(raw)
            if band is None:
                return 0.0, f"Band {i} has a missing or malformed score_range."
            lo, hi = band
            if lo > hi:
                return 0.0, f"Band {i} has minimum {lo} > maximum {hi}."
            bands.append(band)

        bands.sort()
        first_lo: int = bands[0][0]
        last_hi: int = bands[-1][1]
        if first_lo != _SCORE_MIN or last_hi != _SCORE_MAX:
            return 0.0, f"Bands span [{first_lo}, {last_hi}]; expected [{_SCORE_MIN}, {_SCORE_MAX}]."
        for prev, curr in zip(bands, bands[1:], strict=False):
            if curr[0] != prev[1] + 1:
                return 0.0, f"Bands have a gap or overlap between {prev} and {curr}."
        return 1.0, f"{len(bands)} band(s) tile [1, 5] with no gaps or overlaps."


# ---------------------------------------------------------------------------
# 3. StepsWellFormedMetric
# ---------------------------------------------------------------------------


class StepsWellFormedMetric(HybridMetric):
    """`evaluation_steps` must be a non-empty list of short, single-operation strings."""

    name: ClassVar[str] = "steps_well_formed"
    description: ClassVar[str] = (
        "Checks evaluation_steps is non-empty and each step is concise (≤30 words) and starts with an imperative verb."
    )

    _MAX_WORDS: ClassVar[int] = 30
    _IMPERATIVE_HINT_RE: ClassVar[re.Pattern[str]] = re.compile(r"^[A-Z][a-z]+")

    def __init__(self, judge_llm: LiteLLMConfig | None = None) -> None:
        super().__init__(judge_llm)

    def score_case(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> tuple[float, str]:
        parsed: dict[str, Any] | None = _parse_output(output)
        if parsed is None:
            return 0.0, "Output is not parseable JSON; cannot evaluate evaluation_steps."
        steps: object = parsed.get("evaluation_steps")
        if not isinstance(steps, list) or not steps:
            return 0.0, "evaluation_steps is missing or empty."

        problems: list[str] = []
        for i, step in enumerate(steps):
            if not isinstance(step, str) or not step.strip():
                problems.append(f"step {i} is not a non-empty string")
                continue
            word_count: int = len(step.split())
            if word_count > self._MAX_WORDS:
                problems.append(f"step {i} has {word_count} words (limit {self._MAX_WORDS})")
            if not self._IMPERATIVE_HINT_RE.match(step.strip()):
                problems.append(f"step {i} does not start with a capitalized word (imperative form expected)")

        if problems:
            return 0.0, "Step formatting issues: " + "; ".join(problems[:3]) + ("…" if len(problems) > 3 else "")
        return 1.0, f"All {len(steps)} step(s) are concise and imperative-led."


# ---------------------------------------------------------------------------
# 4. ReasoningNonTrivialMetric
# ---------------------------------------------------------------------------


class ReasoningNonTrivialMetric(HybridMetric):
    """`reasoning` must have substance — non-trivial length and not a near-verbatim echo of the criterion."""

    name: ClassVar[str] = "reasoning_non_trivial"
    description: ClassVar[str] = "Checks reasoning is at least 40 characters and not a near-verbatim echo of the criterion."

    _MIN_LEN: ClassVar[int] = 40

    def __init__(self, judge_llm: LiteLLMConfig | None = None) -> None:
        super().__init__(judge_llm)

    def score_case(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> tuple[float, str]:
        parsed: dict[str, Any] | None = _parse_output(output)
        if parsed is None:
            return 0.0, "Output is not parseable JSON; cannot evaluate reasoning."
        reasoning: object = parsed.get("reasoning")
        if not isinstance(reasoning, str) or not reasoning.strip():
            return 0.0, "reasoning is missing or empty."
        text: str = reasoning.strip()
        if len(text) < self._MIN_LEN:
            return 0.0, f"reasoning is only {len(text)} chars (minimum {self._MIN_LEN})."
        criterion_norm: str = " ".join(input.lower().split())
        reasoning_norm: str = " ".join(text.lower().split())
        if criterion_norm and criterion_norm in reasoning_norm and len(reasoning_norm) < len(criterion_norm) * 2:
            return 0.0, "reasoning largely restates the criterion without adding analysis."
        return 1.0, f"reasoning has {len(text)} chars of substantive content."


# ---------------------------------------------------------------------------
# 5. RequiresGroundTruthCorrectMetric
# ---------------------------------------------------------------------------


class RequiresGroundTruthCorrectMetric(HybridMetric):
    """The predicted `requires_ground_truth` flag must match the hand-labeled expected value.

    The ground_truth field on EvalCase is a JSON string with the shape:
        {"requires_ground_truth": true | false}
    """

    name: ClassVar[str] = "requires_ground_truth_correct"
    description: ClassVar[str] = "Checks the predicted requires_ground_truth flag matches the hand-labeled value."

    def __init__(self, judge_llm: LiteLLMConfig | None = None) -> None:
        super().__init__(judge_llm)

    def score_case(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> tuple[float, str]:
        if ground_truth is None:
            return 1.0, "No ground_truth label provided; skipping (vacuous pass)."
        try:
            label_raw: object = json.loads(ground_truth)
        except (json.JSONDecodeError, ValueError):
            return 1.0, "ground_truth is not valid JSON; skipping (vacuous pass)."
        if not isinstance(label_raw, dict):
            return 1.0, "ground_truth is not a dict; skipping (vacuous pass)."
        label_dict: dict[str, Any] = cast(dict[str, Any], label_raw)
        expected: object = label_dict.get("requires_ground_truth")
        if not isinstance(expected, bool):
            return 1.0, "ground_truth has no requires_ground_truth key; skipping."

        parsed: dict[str, Any] | None = _parse_output(output)
        if parsed is None:
            return 0.0, "Output is not parseable JSON; cannot read requires_ground_truth."
        predicted: object = parsed.get("requires_ground_truth")
        if not isinstance(predicted, bool):
            return 0.0, "requires_ground_truth is missing or not a boolean in the output."
        if predicted == expected:
            return 1.0, f"requires_ground_truth correctly predicted as {expected}."
        return 0.0, f"requires_ground_truth predicted {predicted}; expected {expected}."


# ---------------------------------------------------------------------------
# 6. RubricAndStepsCoherentMetric  (pure LLM judge)
# ---------------------------------------------------------------------------


class RubricAndStepsCoherentMetric(BaseLLMJudgeMetric):
    """The evaluation_steps must produce the evidence the rubric bands discriminate on.

    This is the metric that catches the dominant failure mode: steps that measure
    one thing while the rubric judges another, or a rubric whose bands are
    indistinguishable from one another given the steps.
    """

    name: ClassVar[str] = "rubric_and_steps_coherent"
    description: ClassVar[str] = (
        "Checks evaluation steps gather the evidence the rubric bands discriminate on, and that bands are mutually distinguishable."
    )

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        super().__init__(litellm_config)

    def build_system_prompt(self) -> str:
        return (
            "You are an expert evaluator judging whether a G-Eval judging context is internally coherent.\n\n"
            "You will be given:\n"
            "- A <prompt> block: the system prompt that produced the context (the artifact under optimization).\n"
            "- An <input> block: the criterion the factory was asked to build a context for.\n"
            "- An <output> block: the JSON the factory produced (evaluation_steps, scoring_rubric, etc).\n\n"
            "Evaluate two related properties:\n\n"
            "**Step-rubric alignment.** Do the `evaluation_steps` actually gather the evidence needed to "
            "place an output into one of the rubric bands? If the steps measure X but the rubric judges Y, "
            "the context is incoherent — a judge following the steps would have no basis to choose between bands.\n\n"
            "**Band distinguishability.** Are the `expected_outcome` descriptions of adjacent bands "
            "meaningfully different in a way the steps can detect? Bands that read as paraphrases of "
            "each other ('low quality' / 'medium quality' / 'high quality' with no concrete differentiator) "
            "score poorly even if they tile the range.\n\n"
            "Produce a MetricResult with:\n"
            "- score: 1.0 if steps and rubric align tightly and bands are clearly distinguishable; 0.5 for "
            "partial alignment or one or two weak band boundaries; 0.0 for fundamental misalignment\n"
            "- assessment: concise narrative naming the specific alignment or distinguishability issue\n"
            "- signals: one IssueSignal per coherence problem, citing the prompt node whose instructions "
            "should push the factory toward tighter step-rubric alignment\n"
            "- preserve: aspects of the prompt that already produce coherent step-rubric pairs"
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_g_eval_factory_metrics(judge_llm: LiteLLMConfig) -> list[Metric]:
    """Return all 6 evaluation metrics for the g_eval_factory target."""
    return [
        JsonParseableMetric(judge_llm=judge_llm),
        RubricCoversRangeMetric(judge_llm=judge_llm),
        StepsWellFormedMetric(judge_llm=judge_llm),
        ReasoningNonTrivialMetric(judge_llm=judge_llm),
        RequiresGroundTruthCorrectMetric(judge_llm=judge_llm),
        RubricAndStepsCoherentMetric(litellm_config=judge_llm),
    ]
