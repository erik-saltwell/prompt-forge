from __future__ import annotations

import json
from collections.abc import Sequence
from typing import ClassVar

from prompt_model import IssueSignal, MetricResult
from prompt_model.config import LiteLLMConfig
from prompt_model.helpers import acomplete

from ._input_cache import InputData, get_or_add
from ._resources import render_prompt_resource
from .prompt_schemas import PromptAnswers

MAX_SIZE: int = 500
MAX_QUESTION_COUNT: int = 20

TARGET_BEHAVIOR: str = "The output should cover every salient point from the input."
SUCCESS_CRITERION: str = "Every question derived from the input is answerable from the output alone."


async def _generate_answers_from_input_and_questions(
    input: str,
    questions: list[str],
    litellm_config: LiteLLMConfig,
) -> PromptAnswers:
    return await acomplete(
        system_prompt=render_prompt_resource("generate_answers"),
        user_prompt=f"<input>\n{input}\n</input>\n\n<questions>\n{json.dumps(questions)}\n</questions>",
        config=litellm_config,
        response_format=PromptAnswers,
        log_name="summary_input_cache:answers",
    )


def is_yes(input: str) -> bool:
    input_lower = input.lower().strip()
    return input_lower == "yes"


def _truncate(s: str, n: int = MAX_SIZE) -> str:
    if len(s) <= n:
        return s
    return s[:n] + "..."


class CoverageMetric:
    name: ClassVar[str] = "summary_coverage"
    description: ClassVar[str] = "Checks that content in the input is also in the output."

    def __init__(self, litellm_config: LiteLLMConfig) -> None:
        self.litellm_config = litellm_config

    async def evaluate(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> MetricResult:
        input_data: InputData = await get_or_add(input, self.litellm_config)
        questions: list[str] = input_data.questions
        prompt_answers: PromptAnswers = await _generate_answers_from_input_and_questions(output, questions, self.litellm_config)
        answers: Sequence[str] = prompt_answers.answers

        input_snippet: str = _truncate(input) if input.strip() else "(input was empty)"
        output_snippet: str = _truncate(output) if output.strip() else "(output produced no content)"

        if not answers or len(answers) != len(questions):
            score: float = 0.0
            signals: list[IssueSignal] = [
                IssueSignal(
                    culprit_node_id="document",
                    rationale="The model failed to evaluate coverage for this output.",
                    target_behavior=TARGET_BEHAVIOR,
                    success_criterion=SUCCESS_CRITERION,
                    input_snippet=input_snippet,
                    output_snippet=output_snippet,
                )
            ]
            assessment: str = "Coverage could not be evaluated: answer count did not match question count."
            return MetricResult(
                metric_name=self.name,
                score=score,
                assessment=assessment,
                signals=signals,
            )

        yes_count: int = sum(1 for answer in answers if is_yes(answer))
        total: int = len(answers)
        score = float(yes_count) / float(total)
        failed_count: int = total - yes_count

        signals = [
            IssueSignal(
                culprit_node_id="document",
                rationale=f"The output does not cover the following point from the input: {question}",
                target_behavior=TARGET_BEHAVIOR,
                success_criterion=SUCCESS_CRITERION,
                input_snippet=question,
                output_snippet="(the output does not address this point)",
            )
            for question, answer in zip(questions, answers, strict=True)
            if not is_yes(answer)
        ]

        if failed_count == 0:
            assessment = f"All {total} questions answerable from output."
        else:
            assessment = f"{failed_count}/{total} questions not answerable from output."

        return MetricResult(
            metric_name=self.name,
            score=score,
            assessment=assessment,
            signals=signals,
        )
