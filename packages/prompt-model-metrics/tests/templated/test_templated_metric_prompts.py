from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import prompt_model_metrics.templated._templated_llm_metric as metric_module
import pytest
from prompt_model._metrics.protocol import MissingGroundTruthError
from prompt_model.config import LiteLLMConfig
from prompt_model_metrics.templated import PromptContext, ScoreRange, ScoringRubric, TemplatedLLMMetric


def test_build_user_prompt_renders_user_template() -> None:
    metric = TemplatedLLMMetric(PromptContext(criterion="quality"), LiteLLMConfig(model="fake/m"))

    user_prompt: str = metric.build_user_prompt(
        "# Task\n\nDo the thing.\n",
        input="sample input",
        output="sample output",
        ground_truth="ideal output",
    )

    assert not user_prompt.startswith("\n")
    assert "<prompt_text>" in user_prompt
    assert "Do the thing." in user_prompt
    assert "<actual_input>" in user_prompt
    assert "sample input" in user_prompt
    assert "<actual_output>" in user_prompt
    assert "sample output" in user_prompt
    assert "<expected_output>" in user_prompt
    assert "ideal output" in user_prompt


@pytest.mark.parametrize("ground_truth", [None, "", "   \n\t"])
def test_build_user_prompt_omits_optional_expected_output_when_absent(ground_truth: str | None) -> None:
    metric = TemplatedLLMMetric(PromptContext(criterion="quality"), LiteLLMConfig(model="fake/m"))

    user_prompt: str = metric.build_user_prompt(
        "# Task\n\nDo the thing.\n",
        input="sample input",
        output="sample output",
        ground_truth=ground_truth,
    )

    assert "<prompt_text>" in user_prompt
    assert "<actual_input>" in user_prompt
    assert "<actual_output>" in user_prompt
    assert "<expected_output>" not in user_prompt


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("prompt", {"prompt": "", "input": "sample input", "output": "sample output"}),
        ("prompt", {"prompt": "   \n\t", "input": "sample input", "output": "sample output"}),
        ("prompt", {"prompt": None, "input": "sample input", "output": "sample output"}),
        ("input", {"prompt": "# Task\n\nDo it.", "input": "", "output": "sample output"}),
        ("input", {"prompt": "# Task\n\nDo it.", "input": "   \n\t", "output": "sample output"}),
        ("input", {"prompt": "# Task\n\nDo it.", "input": None, "output": "sample output"}),
        ("output", {"prompt": "# Task\n\nDo it.", "input": "sample input", "output": ""}),
        ("output", {"prompt": "# Task\n\nDo it.", "input": "sample input", "output": "   \n\t"}),
        ("output", {"prompt": "# Task\n\nDo it.", "input": "sample input", "output": None}),
    ],
)
def test_evaluate_rejects_missing_required_text(field_name: str, kwargs: dict[str, Any]) -> None:
    metric = TemplatedLLMMetric(PromptContext(criterion="quality"), LiteLLMConfig(model="fake/m"))

    with pytest.raises(ValueError, match=f"{field_name} must be a non-empty string"):
        asyncio.run(metric.evaluate(ground_truth=None, **kwargs))


@pytest.mark.parametrize("ground_truth", [None, "", "   \n\t"])
def test_evaluate_rejects_blank_required_ground_truth(ground_truth: str | None) -> None:
    metric = TemplatedLLMMetric(PromptContext(criterion="quality", requires_ground_truth=True), LiteLLMConfig(model="fake/m"))

    with pytest.raises(MissingGroundTruthError, match="requires ground_truth"):
        asyncio.run(metric.evaluate("# Task\n\nDo it.", "sample input", "sample output", ground_truth))


def test_build_system_prompt_renders_system_template() -> None:
    context = PromptContext(
        criterion="answer concisely",
        definitions=["Concise means no more than two sentences."],
        evaluation_steps=["Check the answer length."],
        scoring_rubric=[ScoringRubric(score_range=ScoreRange(minimum=1, maximum=5), expected_outcome="Clear, concise answer.")],
        important_reminders=["Do not reward verbosity."],
    )
    metric = TemplatedLLMMetric(context, LiteLLMConfig(model="fake/m"))

    system_prompt: str = metric.build_system_prompt("ideal output")

    assert "answer concisely" in system_prompt
    assert not system_prompt.startswith("\n")
    assert "firm but fair LLM prompt evaluator" in system_prompt
    assert "Concise means no more than two sentences." in system_prompt
    assert "Check the answer length." in system_prompt
    assert "Scores 1-5: Clear, concise answer." in system_prompt
    assert "Do not reward verbosity." in system_prompt
    assert "expected_output" in system_prompt
    assert "Return only a JSON object" in system_prompt
    assert '"score": 4' in system_prompt
    assert '"score": 2' in system_prompt
    assert "culprit_node_id" in system_prompt
    assert '"suggested_prompt_change": null' in system_prompt
    assert "unless you are confident in a specific prompt edit" in system_prompt
    assert "fromat" not in system_prompt
    assert "frim" not in system_prompt
    assert "provvided" not in system_prompt


@pytest.mark.parametrize("ground_truth", [None, "", "   \n\t"])
def test_build_system_prompt_omits_optional_blocks_when_context_values_absent(ground_truth: str | None) -> None:
    metric = TemplatedLLMMetric(
        PromptContext(
            criterion="quality",
            evaluation_steps=["Check whether the output is useful."],
        ),
        LiteLLMConfig(model="fake/m"),
    )

    system_prompt: str = metric.build_system_prompt(ground_truth)

    assert "quality" in system_prompt
    assert "Check whether the output is useful." in system_prompt
    assert "<definitions>" not in system_prompt
    assert "<evaluation_rubric>" not in system_prompt
    assert "<important_reminders>" not in system_prompt
    assert "expected_output: A reference output that shows what a good output" not in system_prompt


def test_build_system_prompt_renders_optional_blocks_when_context_values_present() -> None:
    metric = TemplatedLLMMetric(
        PromptContext(
            criterion="quality",
            definitions=["Grounded means supported by the supplied input."],
            evaluation_steps=["Compare output claims to the input."],
            scoring_rubric=[
                ScoringRubric(score_range=ScoreRange(minimum=3, maximum=3), expected_outcome="Partly grounded."),
                ScoringRubric(score_range=ScoreRange(minimum=4, maximum=5), expected_outcome="Fully grounded and useful."),
            ],
            important_reminders=["Penalize unsupported specifics."],
        ),
        LiteLLMConfig(model="fake/m"),
    )

    system_prompt: str = metric.build_system_prompt("ideal output")

    assert "<definitions>" in system_prompt
    assert "Grounded means supported by the supplied input." in system_prompt
    assert "<evaluation_steps>" in system_prompt
    assert "Compare output claims to the input." in system_prompt
    assert "<evaluation_rubric>" in system_prompt
    assert "Score 3: Partly grounded." in system_prompt
    assert "Scores 4-5: Fully grounded and useful." in system_prompt
    assert "Scores 3-3" not in system_prompt
    assert "<important_reminders>" in system_prompt
    assert "Penalize unsupported specifics." in system_prompt
    assert "expected_output: A reference output that shows what a good output" in system_prompt


def test_call_judge_sends_messages_and_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_messages: list[dict[str, str]] = []

    async def stub_acompletion(*, messages: list[dict[str, str]], **kwargs: Any) -> object:
        captured_messages.extend(messages)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"score": 4, "assessment": "solid", "signal": null, "preserve": ["clarity"]}'),
                    logprobs=None,
                )
            ]
        )

    monkeypatch.setattr(metric_module, "_set_response_format", lambda kwargs, response_format: None)
    monkeypatch.setattr(metric_module.litellm, "acompletion", stub_acompletion)

    parsed, raw = asyncio.run(
        metric_module._call_judge(LiteLLMConfig(model="fake/m"), "SYSTEM PROMPT", "USER PROMPT"),
    )

    assert captured_messages == [
        {"role": "system", "content": "SYSTEM PROMPT"},
        {"role": "user", "content": "USER PROMPT"},
    ]
    assert parsed.score == 4
    assert parsed.assessment == "solid"
    assert parsed.preserve == ["clarity"]
    assert raw.choices[0].message.content.startswith('{"score": 4')
