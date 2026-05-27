"""Registry of optimization targets.

Each entry maps a CLI ``--target`` name to a TargetConfig that knows how to
load the seed prompt, the evaluation cases, and the metrics for that target.

Adding a new target:
  1. Create ``targets/<name>/`` with scenarios/ YAML files and metrics.py.
  2. Add an entry to REGISTRY below.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from prompt_model import Metric
from prompt_model._metrics._resources import load_metric_resource
from prompt_model._resources import load_prompt
from prompt_model.config import EvalCase, LiteLLMConfig
from prompt_model_metrics.g_eval._resources import load_resource as load_g_eval_resource
from prompt_model_metrics.self_learning import (
    build_feedback_actor_metrics,
    build_g_eval_factory_metrics,
    build_hybrid_judge_metrics,
    build_structural_actor_metrics,
)

from .targets.feedback_actor._scenario_loader import load_all_scenarios
from .targets.g_eval_factory._scenario_loader import load_all_scenarios as load_g_eval_factory_scenarios
from .targets.hybrid_judge._scenario_loader import load_all_scenarios as load_hybrid_judge_scenarios
from .targets.structural_actor._scenario_loader import load_all_scenarios as load_structural_actor_scenarios

_FEEDBACK_ACTOR_SCENARIOS: Path = Path(__file__).parent / "targets" / "feedback_actor" / "scenarios"
_G_EVAL_FACTORY_SCENARIOS: Path = Path(__file__).parent / "targets" / "g_eval_factory" / "scenarios"
_HYBRID_JUDGE_SCENARIOS: Path = Path(__file__).parent / "targets" / "hybrid_judge" / "scenarios"
_STRUCTURAL_ACTOR_SCENARIOS: Path = Path(__file__).parent / "targets" / "structural_actor" / "scenarios"


@dataclass(frozen=True)
class TargetConfig:
    """Configuration for one optimization target."""

    name: str
    description: str
    seed_prompt_loader: Callable[[], str]
    eval_case_loader: Callable[[], list[EvalCase]]
    metrics_factory: Callable[[LiteLLMConfig], list[Metric]]


REGISTRY: dict[str, TargetConfig] = {
    "feedback-actor": TargetConfig(
        name="feedback-actor",
        description=("Optimize the per-node feedback actor system prompt (prompt_model/_actor/_resources/feedback_actor.md)."),
        seed_prompt_loader=lambda: load_prompt("feedback_actor"),
        eval_case_loader=lambda: load_all_scenarios(_FEEDBACK_ACTOR_SCENARIOS),
        metrics_factory=build_feedback_actor_metrics,
    ),
    "hybrid-judge": TargetConfig(
        name="hybrid-judge",
        description="Optimize the hybrid judge system prompt (prompt_model/_metrics/_resources/hybrid_judge.md).",
        seed_prompt_loader=lambda: load_metric_resource("hybrid_judge"),
        eval_case_loader=lambda: load_hybrid_judge_scenarios(_HYBRID_JUDGE_SCENARIOS),
        metrics_factory=build_hybrid_judge_metrics,
    ),
    "g-eval-factory": TargetConfig(
        name="g-eval-factory",
        description=(
            "Optimize the G-Eval context_factory system prompt "
            "(prompt_model_metrics/g_eval/_resources/context_factory_prompt.md). "
            "The factory turns a natural-language criterion into a structured judging context "
            "(evaluation_steps, scoring_rubric, requires_ground_truth)."
        ),
        seed_prompt_loader=lambda: load_g_eval_resource("context_factory_prompt"),
        eval_case_loader=lambda: load_g_eval_factory_scenarios(_G_EVAL_FACTORY_SCENARIOS),
        metrics_factory=build_g_eval_factory_metrics,
    ),
    "structural-actor": TargetConfig(
        name="structural-actor",
        description="Optimize the structural cleanup actor system prompt (prompt_model/_resources/structural_actor.md).",
        seed_prompt_loader=lambda: load_prompt("structural_actor"),
        eval_case_loader=lambda: load_structural_actor_scenarios(_STRUCTURAL_ACTOR_SCENARIOS),
        metrics_factory=build_structural_actor_metrics,
    ),
}
