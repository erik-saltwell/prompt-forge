from __future__ import annotations

from typing import NamedTuple

from pydantic import BaseModel, Field

SCORE_MIN: int = 1
SCORE_MAX: int = 5


class ScoreRange(NamedTuple):
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

    def to_context(self, criterion: str) -> PromptContext:
        return PromptContext(
            criterion=criterion,
            evaluation_steps=list(self.evaluation_steps),
            scoring_rubric=list(self.scoring_rubric),
            requires_ground_truth=self.requires_ground_truth,
        )
