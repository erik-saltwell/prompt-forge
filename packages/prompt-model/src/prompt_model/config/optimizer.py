import json
import typing
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from .eval_case import EvalCase
from .llm import LiteLLMConfig
from .strategies import (
    PromptRenderStrategyOption,
    RedactionStrategyOption,
    SignalRenderStrategyOption,
    StructuralCleanupOption,
)


class OptimizerConfig(BaseModel):
    """Top-level configuration for `optimize_prompt`.

    Holds only primitives and collections of primitives so it can be loaded from YAML at the apps
    layer. Code objects (metrics, reward strategy, progress reporter) are passed as separate
    arguments to `optimize_prompt`.

    Effectively immutable: `frozen=True` makes attribute assignment raise; all `.with_*` helpers
    return a new instance via `model_copy(update=...)`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    seed_prompt: str = Field(description="The initial prompt to optimize, as conforming markdown.")
    eval_cases: list[EvalCase] = Field(
        default_factory=list,
        description="Evaluation cases the optimizer scores candidates against.",
    )
    target_llm: LiteLLMConfig = Field(description="LLM that runs the prompt under optimization to produce outputs.")
    actor_llm: LiteLLMConfig = Field(description="LLM that emits structural mutation actions for the prompt.")
    structural_llm: LiteLLMConfig | None = Field(
        default=None,
        description="LLM for the actor's structural cleanup pass; falls back to actor_llm when omitted.",
    )
    judge_llm: LiteLLMConfig = Field(
        description="Default LLM used by LLM-judge metrics. Individual metrics may override with their own LiteLLMConfig.",
    )
    iterations: int = Field(default=8, gt=0, description="Number of optimization iterations.")
    top_k_per_iteration: int = Field(default=3, gt=0, description="Candidates carried forward to refinement each iteration.")
    floor: int = Field(default=2, gt=0, description="Minimum number of evaluations per candidate before UCB allocates extras.")
    ucb_budget: int = Field(default=20, ge=0, description="Extra evaluations allocated by UCB1 beyond the floor.")
    seed_warmup_pulls: int = Field(
        default=2,
        gt=0,
        description="Pre-loop evaluations applied to the seed prompt before the first revise.",
    )
    max_children_per_parent: int = Field(
        default=3,
        gt=0,
        description="Cap on revise children produced per surviving parent per iteration.",
    )
    min_improvement_delta: float = Field(
        default=0.005,
        ge=0.0,
        description="Minimum best-score improvement over `early_stop_patience` iterations before early-stop fires.",
    )
    early_stop_patience: int = Field(
        default=3,
        gt=0,
        description="Iterations of no-improvement (per `min_improvement_delta`) before terminating early.",
    )
    max_llm_concurrency: int = Field(
        default=4,
        gt=0,
        description="Maximum concurrent LLM calls during evaluation and revise phases.",
    )
    exploration_bonus: float = Field(
        default=1.0,
        ge=0.0,
        description="Multiplier for UCB1's exploration term; higher values sample less-tested candidates more aggressively.",
    )
    error_budget: int = Field(
        default=0,
        ge=0,
        description=(
            "Per-iteration tolerance for failed evaluation pulls; the iteration's evaluation phase "
            "raises once the count exceeds this budget. Resets at the start of each iteration."
        ),
    )
    seed: int | None = Field(
        default=None,
        description="Optional RNG seed for case-shuffle and UCB tiebreaks. None = nondeterministic.",
    )

    # --- Strategy selectors ---------------------------------------------------

    redaction_strategy: RedactionStrategyOption = Field(
        default=RedactionStrategyOption.DEFAULT,
        description=(
            "Controls how much of the prompt tree the actor LLM sees. "
            "'default' shows only the culprit, ancestors, siblings, and section headings; "
            "'none' shows the entire tree verbatim."
        ),
    )
    prompt_render_strategy: PromptRenderStrategyOption = Field(
        default=PromptRenderStrategyOption.XML,
        description=(
            "Serialization format the actor LLM reads the prompt tree in. "
            "'xml' (default) is recommended for Claude; 'json' uses Pydantic model_dump; "
            "'markdown' uses critic-form markdown with HTML-comment ID overlays."
        ),
    )
    signal_render_strategy: SignalRenderStrategyOption = Field(
        default=SignalRenderStrategyOption.MARKDOWN,
        description=(
            "Format used to render aggregated issue signals in the actor's user prompt. "
            "'markdown' (default) produces humanized subsections; 'json' and 'xml' are structured alternatives."
        ),
    )
    structural_cleanup: StructuralCleanupOption = Field(
        default=StructuralCleanupOption.ALWAYS,
        description=(
            "Controls when the structural cleanup LLM pass runs after the per-node feedback pass. "
            "'always' (default) runs it unconditionally; 'never' skips it; "
            "'on_structural_actions' triggers on insert/delete/move; 'on_move_actions' triggers on move only."
        ),
    )

    @classmethod
    def from_yaml(cls, path: Path | str, **kwargs: typing.Any) -> Self:
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f)
        if data is None:
            data = {}
        data.update(kwargs)
        return cls.model_validate(data)

    def with_seed_prompt(self, prompt: str) -> Self:
        return self.model_copy(update={"seed_prompt": prompt})

    def with_seed_prompt_from_path(self, path: Path) -> Self:
        return self.model_copy(update={"seed_prompt": Path(path).read_text()})

    def with_eval_case(
        self,
        *,
        input: str,
        ground_truth: str | None = None,
        retrieval_context: list[str] | None = None,
    ) -> Self:
        new_case: EvalCase = EvalCase(input=input, ground_truth=ground_truth, retrieval_context=retrieval_context)
        return self.model_copy(update={"eval_cases": [*self.eval_cases, new_case]})

    def with_eval_cases(self, cases: list[EvalCase]) -> Self:
        return self.model_copy(update={"eval_cases": list(cases)})

    def with_eval_cases_from_jsonl(self, path: Path) -> Self:
        loaded: list[EvalCase] = []
        for line in Path(path).read_text().splitlines():
            stripped: str = line.strip()
            if not stripped:
                continue
            loaded.append(EvalCase.model_validate(json.loads(stripped)))
        return self.model_copy(update={"eval_cases": loaded})

    def with_target_llm(self, cfg: LiteLLMConfig) -> Self:
        return self.model_copy(update={"target_llm": cfg})

    def with_actor_llm(self, cfg: LiteLLMConfig) -> Self:
        return self.model_copy(update={"actor_llm": cfg})

    def with_judge_llm(self, cfg: LiteLLMConfig) -> Self:
        return self.model_copy(update={"judge_llm": cfg})

    def with_iterations(self, n: int) -> Self:
        return self.model_copy(update={"iterations": n})

    def with_top_k_per_iteration(self, n: int) -> Self:
        return self.model_copy(update={"top_k_per_iteration": n})

    def with_floor(self, n: int) -> Self:
        return self.model_copy(update={"floor": n})

    def with_ucb_budget(self, n: int) -> Self:
        return self.model_copy(update={"ucb_budget": n})

    def with_max_llm_concurrency(self, n: int) -> Self:
        return self.model_copy(update={"max_llm_concurrency": n})

    def with_structural_llm(self, cfg: LiteLLMConfig | None) -> Self:
        return self.model_copy(update={"structural_llm": cfg})

    def with_seed_warmup_pulls(self, n: int) -> Self:
        return self.model_copy(update={"seed_warmup_pulls": n})

    def with_max_children_per_parent(self, n: int) -> Self:
        return self.model_copy(update={"max_children_per_parent": n})

    def with_min_improvement_delta(self, v: float) -> Self:
        return self.model_copy(update={"min_improvement_delta": v})

    def with_early_stop_patience(self, n: int) -> Self:
        return self.model_copy(update={"early_stop_patience": n})

    def with_seed(self, n: int | None) -> Self:
        return self.model_copy(update={"seed": n})

    def with_redaction_strategy(self, option: RedactionStrategyOption) -> Self:
        return self.model_copy(update={"redaction_strategy": option})

    def with_prompt_render_strategy(self, option: PromptRenderStrategyOption) -> Self:
        return self.model_copy(update={"prompt_render_strategy": option})

    def with_signal_render_strategy(self, option: SignalRenderStrategyOption) -> Self:
        return self.model_copy(update={"signal_render_strategy": option})

    def with_structural_cleanup(self, option: StructuralCleanupOption) -> Self:
        return self.model_copy(update={"structural_cleanup": option})
