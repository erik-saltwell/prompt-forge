from __future__ import annotations

from typing import ClassVar

from prompt_model import IssueSignal, MetricResult
from prompt_model._metrics.base_llm_judge import RenderPromptStrategy
from prompt_model._prompt import parse_from_string
from prompt_model.config import LiteLLMConfig
from prompt_model.helpers import acomplete
from prompt_model.strategies.prompt_rendering_strategy import MarkdownRenderPromptStrategy

from ._input_cache import InputData, get_or_add
from ._resources import render_prompt_resource
from .prompt_schemas import ClaimVerdict, ClaimVerdicts, PromptClaims

MAX_SIZE: int = 500

TARGET_BEHAVIOR: str = "The output should only assert facts supported by or consistent with the source text."
SUCCESS_CRITERION: str = "Every factual claim in the output is entailed by or consistent with the source."


def _truncate(s: str, n: int = MAX_SIZE) -> str:
    if len(s) <= n:
        return s
    return s[:n] + "..."


def _is_yes(v: str) -> bool:
    return v.lower().strip() == "yes"


async def _generate_claims_from_output(output: str, litellm_config: LiteLLMConfig) -> PromptClaims:
    return await acomplete(
        system_prompt=render_prompt_resource("generate_claims"),
        user_prompt=f"<input>\n{output}\n</input>",
        config=litellm_config,
        response_format=PromptClaims,
        log_name="summary_alignment:output_claims",
    )


def _build_user_prompt(input_claims: list[str], output_claims: list[str], rendered_prompt: str) -> str:
    input_text: str = "\n".join(f"- {c}" for c in input_claims) if input_claims else "(no claims extracted)"
    output_text: str = "\n".join(f"- {c}" for c in output_claims) if output_claims else "(no claims extracted)"
    return (
        f"<prompt>\n{rendered_prompt}\n</prompt>\n\n"
        f"<source_claims>\n{input_text}\n</source_claims>\n\n"
        f"<output_claims>\n{output_text}\n</output_claims>"
    )


class AlignmentMetric:
    name: ClassVar[str] = "summary_alignment"
    description: ClassVar[str] = "Checks that output claims are faithful to the input source text."

    def __init__(
        self,
        litellm_config: LiteLLMConfig,
        render_strategy: RenderPromptStrategy | None = None,
    ) -> None:
        self.litellm_config: LiteLLMConfig = litellm_config
        self.render_strategy: RenderPromptStrategy = render_strategy if render_strategy is not None else MarkdownRenderPromptStrategy()

    async def evaluate(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> MetricResult:
        input_data: InputData = await get_or_add(input, self.litellm_config)
        input_claims: list[str] = input_data.truths

        output_claims: list[str] = (await _generate_claims_from_output(output, self.litellm_config)).claims

        if not output_claims:
            input_snippet: str = _truncate(input) if input.strip() else "(input was empty)"
            output_snippet: str = _truncate(output) if output.strip() else "(output produced no content)"
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                assessment="No output claims could be extracted; alignment could not be evaluated.",
                signals=[
                    IssueSignal(
                        culprit_node_id="document",
                        rationale="The output produced no extractable factual claims.",
                        target_behavior=TARGET_BEHAVIOR,
                        success_criterion=SUCCESS_CRITERION,
                        input_snippet=input_snippet,
                        output_snippet=output_snippet,
                    )
                ],
            )

        document = parse_from_string(prompt)
        rendered_prompt: str = self.render_strategy.render(document, focus_ids=None)
        system_prompt: str = render_prompt_resource("score_alignment", format_description=self.render_strategy.describe_format())
        user_prompt: str = _build_user_prompt(input_claims, output_claims, rendered_prompt)

        result: ClaimVerdicts = await acomplete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=self.litellm_config,
            response_format=ClaimVerdicts,
            log_name="summary_alignment:score",
        )

        verdicts: list[ClaimVerdict] = result.verdicts
        input_snippet: str = _truncate(input) if input.strip() else "(input was empty)"
        output_snippet: str = _truncate(output) if output.strip() else "(output produced no content)"

        if not verdicts or len(verdicts) != len(output_claims):
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                assessment="Alignment could not be evaluated: verdict count did not match output claim count.",
                signals=[
                    IssueSignal(
                        culprit_node_id="document",
                        rationale="The model failed to evaluate alignment for this output.",
                        target_behavior=TARGET_BEHAVIOR,
                        success_criterion=SUCCESS_CRITERION,
                        input_snippet=input_snippet,
                        output_snippet=output_snippet,
                    )
                ],
            )

        yes_count: int = sum(1 for v in verdicts if _is_yes(v.supported))
        total: int = len(verdicts)
        score: float = float(yes_count) / float(total)
        failed_count: int = total - yes_count

        signals: list[IssueSignal] = [
            IssueSignal(
                culprit_node_id=v.culprit_node_id or "document",
                rationale=v.rationale or f"Output claim contradicts the source: {v.claim}",
                target_behavior=TARGET_BEHAVIOR,
                success_criterion=SUCCESS_CRITERION,
                input_snippet=v.conflicting_input_claim or input_snippet,
                output_snippet=v.claim,
                suggested_prompt_change=v.suggested_prompt_change,
            )
            for v in verdicts
            if not _is_yes(v.supported)
        ]

        if failed_count == 0:
            assessment: str = f"All {total} output claims are faithful to the source."
        else:
            assessment = f"{failed_count}/{total} output claims contradict the source."

        return MetricResult(
            metric_name=self.name,
            score=score,
            assessment=assessment,
            signals=signals,
        )
