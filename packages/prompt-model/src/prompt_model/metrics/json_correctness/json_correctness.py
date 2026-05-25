"""JsonCorrectnessMetric — deterministic JSON validity check with LLM judge on failure."""

from __future__ import annotations

import json
from typing import ClassVar

from ..._metrics.hybrid_metric import HybridMetric
from ...config import LiteLLMConfig


class JsonCorrectnessMetric(HybridMetric):
    """Checks whether the model output is valid JSON.

    Score is determined deterministically:
    - 1.0 if the output parses as valid JSON
    - 0.0 if it does not

    When the score is 0.0 and a judge LLM is configured, the judge fires and
    produces an `IssueSignal` localized to the prompt node most likely causing
    the malformed output (e.g. missing or ambiguous format instructions).
    """

    name: ClassVar[str] = "json_correctness"
    description: ClassVar[str] = "Checks that the model output is valid JSON."

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        super().__init__(judge_llm=litellm_config)

    def score_case(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> tuple[float, str]:
        try:
            json.loads(output)
            return 1.0, "Output is valid JSON."
        except (json.JSONDecodeError, ValueError) as exc:
            return 0.0, f"Output is not valid JSON: {exc}"
