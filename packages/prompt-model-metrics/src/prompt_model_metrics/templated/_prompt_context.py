from __future__ import annotations

from pydantic import BaseModel, Field

SCORE_MIN: int = 1
SCORE_MAX: int = 5


class ScoreRange(BaseModel):
    minimum: int
    maximum: int


class ScoringRubric(BaseModel):
    score_range: ScoreRange
    expected_outcome: str


class PromptContext(BaseModel):
    criterion: str
    evaluation_steps: list[str] = Field(default_factory=list)
    scoring_rubric: list[ScoringRubric] = Field(default_factory=list)
    requires_ground_truth: bool = False
    definitions: list[str] = Field(default_factory=list)
    important_reminders: list[str] = Field(default_factory=list)

    def normalize_score(self, score: float) -> float:
        if score < SCORE_MIN or score > SCORE_MAX:
            raise ValueError(f"Cannot normalize score {score} because it is outside the range of [{SCORE_MIN}, {SCORE_MAX}]")
        return (score - SCORE_MIN) / (SCORE_MAX - SCORE_MIN)


class PromptContextDraft(BaseModel):
    """Factory-LLM response shape. `reasoning` is declared first to condition the rest of the output on it."""

    reasoning: str = Field(description="Short rationale for the produced evaluation steps, rubric, and ground-truth flag.")
    evaluation_steps: list[str] = Field(
        description="Ordered reasoning steps the judge should follow. At least one entry.",
        min_length=1,
    )
    scoring_rubric: list[ScoringRubric] = Field(
        description="Banded rubric covering the 1-5 score range. Bands may be coarse. At least one entry.",
        min_length=1,
    )
    requires_ground_truth: bool = Field(
        description="True iff the criterion is reference-based and cannot be judged without a ground-truth value.",
    )
    definitions: list[str] = Field(
        default_factory=list,
        description=(
            "Optional definitions of important terms used in the criterion or evaluation steps. "
            "Include only when a term is ambiguous, domain-specific, or used in a non-obvious way; "
            "leave empty otherwise."
        ),
    )
    important_reminders: list[str] = Field(
        default_factory=list,
        description=(
            "Optional last-mile reminders shown to the judge immediately before it scores. "
            "Use for high-leverage cautions a judge might overlook (e.g. common false-positive patterns, "
            "edge cases the rubric depends on). Leave empty if nothing warrants restating."
        ),
    )

    def to_context(self, criterion: str) -> PromptContext:
        return PromptContext(
            criterion=criterion,
            evaluation_steps=list(self.evaluation_steps),
            scoring_rubric=list(self.scoring_rubric),
            requires_ground_truth=self.requires_ground_truth,
            definitions=list(self.definitions),
            important_reminders=list(self.important_reminders),
        )
