from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EvalCase(BaseModel):
    """One evaluation input. See docs/batch-testing.md."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input: str = Field(...)
    ground_truth: str | None = Field(default=None)
    retrieval_context: list[str] | None = Field(default=None)
