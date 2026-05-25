"""Per-case correctness metric for SCULPT's Causal Judgement task.

The parser mirrors SCULPT (`src/sculpt/tasks.py::BBHCausalJudgementTask`):
the model's output is `.lower().strip()` and must equal `"yes"` or `"no"`.
Anything else is treated as a miss.

Score is 1.0 on match, 0.0 otherwise — the optimizer's mean-aggregation across
cases then approximates accuracy as the optimization signal. Weighted F1 is
computed separately in `headline.py` after optimization finishes.
"""

from __future__ import annotations

from typing import ClassVar

from prompt_model import IssueSignal, MetricResult, MissingGroundTruthError


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


class CausalJudgementCorrectness:
    """Per-case binary correctness metric for SCULPT CJ.

    Returns 1.0 on exact match against ``ground_truth`` (lower-stripped, "yes"/"no").
    Returns 0.0 otherwise — including when the model output cannot be parsed.

    On miss, emits a single `IssueSignal` accusing the document (no localizable node)
    so the critic has something to chew on. The signal records what was expected
    and what was produced.
    """

    name: ClassVar[str] = "cj_correctness"
    description: ClassVar[str] = (
        "Causal Judgement binary correctness: model output must parse to exactly 'yes' or 'no' and match the ground truth."
    )

    async def evaluate(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> MetricResult:
        if ground_truth is None:
            raise MissingGroundTruthError("CausalJudgementCorrectness requires ground_truth on every EvalCase")

        predicted: str | None = parse_yes_no(output)
        expected: str = ground_truth.lower().strip()

        if predicted == expected:
            return MetricResult(
                metric_name=self.name,
                score=1.0,
                assessment=f"Correct: predicted '{predicted}' matches ground truth.",
            )

        if predicted is None:
            rationale: str = f"Output did not parse to 'yes' or 'no' (got: '{_truncate(output)}'). Expected '{expected}'."
            target: str = "Always end the response with exactly the single word 'Yes' or 'No' and nothing else."
        else:
            rationale = f"Predicted '{predicted}' but ground truth is '{expected}'."
            target = "Reason more carefully about which causal-judgement convention applies before answering."

        return MetricResult(
            metric_name=self.name,
            score=0.0,
            assessment=rationale,
            signals=[
                IssueSignal(
                    culprit_node_id="document",
                    rationale=rationale,
                    target_behavior=target,
                    success_criterion=f"Response on this case is exactly '{expected.capitalize()}'.",
                    input_snippet=_truncate(input),
                    output_snippet=_truncate(output) or "(empty)",
                )
            ],
        )
