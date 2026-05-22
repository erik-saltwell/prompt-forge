import json
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from .eval_case import EvalCase
from .llm import LiteLLMConfig


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
    judge_llm: LiteLLMConfig = Field(
        description="Default LLM used by LLM-judge metrics. Individual metrics may override with their own LiteLLMConfig.",
    )
    iterations: int = Field(default=8, gt=0, description="Number of optimization iterations.")
    top_k_per_iteration: int = Field(default=3, gt=0, description="Candidates carried forward to refinement each iteration.")
    floor: int = Field(default=2, gt=0, description="Minimum number of evaluations per candidate before UCB allocates extras.")
    ucb_budget: int = Field(default=20, ge=0, description="Extra evaluations allocated by UCB1 beyond the floor.")
    max_concurrency: int = Field(default=4, gt=0, description="Maximum concurrent LLM calls during batch evaluation.")

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

    def with_max_concurrency(self, n: int) -> Self:
        return self.model_copy(update={"max_concurrency": n})
