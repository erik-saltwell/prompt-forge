from pydantic import BaseModel, Field


class EvalCase(BaseModel):
    """One evaluation input. Metrics needing `ground_truth` or `retrieval_context` read them from here."""

    input: str = Field(description="The input passed to the target LLM alongside the prompt.")
    ground_truth: str | None = Field(default=None, description="Reference output for metrics that compare against a gold answer.")
    retrieval_context: list[str] | None = Field(
        default=None,
        description="Retrieved chunks for RAG-style metrics like contextual recall / faithfulness.",
    )
