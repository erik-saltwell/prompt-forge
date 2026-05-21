from __future__ import annotations

from pydantic import BaseModel, Field

from .._utils import pydantic_aliases as py_types


class ImprovementGuidance(BaseModel):
    target_behavior: str = Field(
        pattern=r".*\S.*",
        description="What behavior we want to get out of the prompt from this improvement.",
    )
    success_criterion: str = Field(
        pattern=r".*\S.*",
        description="The criterion which, if met, represents a succesful change to the prompt.",
    )
    suggested_prompt_change: str | None = Field(
        default=None,
        pattern=r".*\S.*",
        description="Optional. A general description of how to change the prompt to achieve the target behavior. "
        "Omit when the metric can identify the issue but is not confident in a specific fix.",
    )


class IssueSignal(BaseModel):
    suspected_culprit_prompt_nodes: list[str] = Field(
        default_factory=list,
        description="Hierarchical IDs of prompt nodes likely causing the issue. "
        "May be empty when the issue is not localizable to specific nodes (e.g., a whole-prompt concern).",
    )

    relevant_input_snippets: list[str] = Field(
        default_factory=list,
        description="Snippets taken from the input that are evidence of this issue. Provides context later to the actor llm.",
    )
    relevant_output_snippets: list[str] = Field(
        default_factory=list,
        description="Snippets taken from the output that are evidence of this issue. Provides context later to the actor llm.",
    )

    suspected_prompt_rationale: str = Field(
        pattern=r".*\S.*",
        description="The reason to believe why the suspected culprit prompt node is causing the issue.",
    )
    improvement: ImprovementGuidance


class MetricResult(BaseModel):
    score: py_types.ZeroToOneFloat = Field(
        description="The score for this metric in the range [0,1.0]. Higher is better. Pass/fail metrics encode as 1.0 / 0.0.",
    )
    assessment: str = Field(
        pattern=r".*\S.*",
        description="Narrative summary of this metric's judgment for the case. "
        "Present at every score level — it describes either what the metric approved of or it summarizes the problem.",
    )
    signals: list[IssueSignal] = Field(
        default_factory=list,
        description="Specific evidenced complaints about the prompt found in this evaluation. Empty when no issues found.",
    )
    preserve: list[str] = Field(
        default_factory=list,
        description="Properties of the current prompt that are working and should not be broken by any subsequent edit. "
        "Applies regardless of score.",
    )
