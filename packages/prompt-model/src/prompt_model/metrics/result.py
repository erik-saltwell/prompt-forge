from pydantic import BaseModel, Field

from .._utils import pydantic_aliases as py_types


class IssueSignal(BaseModel):
    culprit_node_id: py_types.NonBlankStr = Field(
        description="Hierarchical id of the prompt node accused of causing the issue, "
        "or the literal 'document' sentinel when the issue is not localizable to a specific node.",
    )
    rationale: py_types.NonBlankStr = Field(
        description="Why the accused node is at fault.",
    )
    target_behavior: py_types.NonBlankStr = Field(
        description="What behavior we want to get out of the prompt from this improvement.",
    )
    success_criterion: py_types.NonBlankStr = Field(
        description="The criterion which, if met, represents a successful change to the prompt.",
    )
    suggested_prompt_change: str | None = Field(
        default=None,
        pattern=r".*\S.*",
        description="Optional. A general description of how to change the prompt to achieve the target behavior. "
        "Omit when the metric can identify the issue but is not confident in a specific fix.",
    )
    input_snippet: py_types.NonBlankStr = Field(
        description="Verbatim quote from the case's input that evidences the issue. Never paraphrased.",
    )
    output_snippet: py_types.NonBlankStr = Field(
        description="Verbatim quote from the case's output that evidences the issue. Never paraphrased.",
    )
    seen_in_n_cases: int = Field(
        default=1,
        ge=1,
        description="Number of distinct evaluation cases this signal collapses across after aggregation. "
        "Defaults to 1 on critic emission; the aggregator increments on dedupe.",
    )


class MetricResult(BaseModel):
    score: py_types.ZeroToOneFloat = Field(
        description="The score for this metric in the range [0,1.0]. Higher is better. Pass/fail metrics encode as 1.0 / 0.0.",
    )
    assessment: py_types.NonBlankStr = Field(
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
