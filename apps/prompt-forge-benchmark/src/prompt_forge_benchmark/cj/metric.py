"""Per-case correctness metric for SCULPT's Causal Judgement task.

Hybrid: deterministic score (`HybridMetric.score_case`) plus an LLM judge
on miss that generates a localized `IssueSignal`. The parser mirrors SCULPT
(`src/sculpt/tasks.py::BBHCausalJudgementTask`): the model's output is
`.lower().strip()` and must equal `"yes"` or `"no"`. Anything else is a miss.
Weighted F1 is computed separately in `headline.py` after optimization
finishes.
"""

from __future__ import annotations

from typing import ClassVar

from prompt_model import HybridMetric, MissingGroundTruthError


def parse_yes_no(raw: str) -> str | None:
    """Return ``"yes"`` / ``"no"`` if the (lower-stripped) output matches; otherwise ``None``.

    Matches SCULPT's parser exactly — equality check on a single normalized token.
    Outputs that contain extra prose (e.g. "Yes, because...") do NOT parse, mirroring SCULPT.
    """
    normalized: str = raw.lower().strip()
    if normalized == "yes":
        return "yes"
    if normalized == "no":
        return "no"
    return None


def _truncate(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


class CausalJudgementCorrectness(HybridMetric):
    """Per-case binary correctness for SCULPT CJ."""

    name: ClassVar[str] = "cj_correctness"
    description: ClassVar[str] = (
        "Causal Judgement binary correctness: model output must parse to exactly 'yes' or 'no' and match the ground truth."
    )

    def score_case(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> tuple[float, str]:
        if ground_truth is None:
            raise MissingGroundTruthError("CausalJudgementCorrectness requires ground_truth on every EvalCase")

        predicted: str | None = parse_yes_no(output)
        expected: str = ground_truth.lower().strip()

        if predicted == expected:
            return 1.0, f"Correct: predicted '{predicted}' matches ground truth."
        if predicted is None:
            return 0.0, f"Output did not parse to 'yes' or 'no' (got: '{_truncate(output)}'). Expected '{expected}'."
        return 0.0, f"Predicted '{predicted}' but ground truth is '{expected}'."
