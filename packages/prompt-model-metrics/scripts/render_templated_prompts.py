from __future__ import annotations

import argparse
from pathlib import Path

from prompt_model.config import LiteLLMConfig
from prompt_model_metrics.templated import PromptContext, ScoreRange, ScoringRubric, TemplatedLLMMetric


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the templated metric judge prompts with representative data.")
    parser.add_argument("--output", type=Path, help="Optional path to write the rendered prompts as Markdown.")
    args = parser.parse_args()

    metric = TemplatedLLMMetric(
        context=PromptContext(
            criterion="The answer should be grounded in the supplied input and avoid unsupported specifics.",
            definitions=["Grounded means every concrete claim in the output is supported by the supplied input."],
            evaluation_steps=[
                "Identify the concrete claims in the actual output.",
                "Compare each claim against the actual input and expected output.",
                "Assign a score using the rubric and explain the most important reason.",
            ],
            scoring_rubric=[
                ScoringRubric(
                    score_range=ScoreRange(minimum=1, maximum=2),
                    expected_outcome="Mostly unsupported or contradicts the input.",
                ),
                ScoringRubric(
                    score_range=ScoreRange(minimum=3, maximum=3),
                    expected_outcome="Partly grounded, but includes important unsupported details.",
                ),
                ScoringRubric(
                    score_range=ScoreRange(minimum=4, maximum=5),
                    expected_outcome="Fully grounded and useful, with no meaningful unsupported details.",
                ),
            ],
            requires_ground_truth=True,
            important_reminders=[
                "Do not reward fluent wording when the facts are unsupported.",
                "Use the signal field only when the prompt itself appears responsible for the failure.",
            ],
        ),
        judge_llm_config=LiteLLMConfig(model="fake/model"),
    )

    prompt = """# Answering Rules

Use only the supplied source text. If the source text does not contain the answer, say that the answer is not available.
"""
    actual_input = "Source: The rollout starts on Tuesday for beta users in Canada and Germany."
    actual_output = "The rollout starts Monday for all users in Canada, Germany, and France."
    expected_output = "The rollout starts on Tuesday for beta users in Canada and Germany."

    system_prompt = metric.build_system_prompt(expected_output)
    user_prompt = metric.build_user_prompt(prompt, actual_input, actual_output, expected_output)
    rendered = f"# System Prompt\n\n```text\n{system_prompt}\n```\n\n# User Prompt\n\n```text\n{user_prompt}\n```\n"

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
