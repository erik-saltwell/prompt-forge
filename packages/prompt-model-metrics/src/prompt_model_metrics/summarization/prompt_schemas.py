from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

YesOrNo = Literal["yes", "no", "Yes", "No", "YES", "NO"]
FailureTypeStr = Literal["contradiction", "unsupported"] | None


class PromptAnswers(BaseModel):
    answers: list[YesOrNo]


class PromptQuestions(BaseModel):
    questions: list[str]


class PromptClaims(BaseModel):
    claims: list[str]


class ClaimVerdict(BaseModel):
    claim: str
    supported: YesOrNo
    rationale: str | None = None
    culprit_node_id: str | None = None
    conflicting_input_claim: str | None = None
    suggested_prompt_change: str | None = None
    failure_type: FailureTypeStr


class ClaimVerdicts(BaseModel):
    verdicts: list[ClaimVerdict]
