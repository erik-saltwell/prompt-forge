from pydantic import BaseModel, Field


class CandidateSummary(BaseModel):
    """One candidate's row in the final result. The prompt is conforming markdown — the parsed
    `Document` form is private to the optimizer."""

    prompt: str = Field(description="The candidate prompt as conforming markdown.")
    score: float = Field(ge=0.0, le=1.0, description="Aggregated reward in [0, 1].")
    metrics: dict[str, float] = Field(
        default_factory=dict,
        description="Per-metric mean score across this candidate's evaluations, keyed by metric_name.",
    )


class OptimizeResult(BaseModel):
    """What `optimize_prompt` returns."""

    best_prompt: str = Field(description="Highest-scoring candidate prompt, as conforming markdown.")
    best_score: float = Field(ge=0.0, le=1.0, description="The aggregated reward of `best_prompt`.")
    best_metrics: dict[str, float] = Field(
        default_factory=dict,
        description="Per-metric mean score for the best candidate, keyed by metric_name.",
    )
    top_k: list[CandidateSummary] = Field(
        default_factory=list,
        description="Top candidates from the final iteration, ranked descending. `top_k[0]` is the best.",
    )
    iterations_run: int = Field(ge=0, description="How many iterations actually ran (may be less than requested).")
    total_errors: int = Field(ge=0, default=0, description="Non-fatal failures (metric/actor) observed across the run.")
