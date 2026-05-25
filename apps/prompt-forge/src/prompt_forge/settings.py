from pathlib import Path

import yaml
from prompt_model.config import LiteLLMConfig
from pydantic import BaseModel, Field


class MetricConfig(BaseModel):
    name: str
    description: str
    rubric: str


class PromptForgeSettings(BaseModel):
    target_llm: LiteLLMConfig
    actor_llm: LiteLLMConfig
    judge_llm: LiteLLMConfig

    eval_data_dir: str | None = None
    metrics: list[MetricConfig] = Field(default_factory=list)

    iterations: int = 8
    early_stop_patience: int = 3
    max_llm_concurrency: int = 4
    top_k_per_iteration: int = 3
    floor: int = 2
    ucb_budget: int = 20
    seed_warmup_pulls: int = 2
    max_children_per_parent: int = 3
    min_improvement_delta: float = 0.005
    exploration_bonus: float = 1.0
    error_budget: int = 0
    seed: int | None = None

    @classmethod
    def load(cls, path: str | Path) -> "PromptForgeSettings":
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls.model_validate(data)
