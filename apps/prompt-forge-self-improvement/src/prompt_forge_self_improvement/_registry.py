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
from prompt_model._resources import load_prompt
from prompt_model.config import EvalCase, LiteLLMConfig

from .targets.feedback_actor._scenario_loader import load_all_scenarios
from .targets.feedback_actor.metrics import build_feedback_actor_metrics

_FEEDBACK_ACTOR_SCENARIOS: Path = Path(__file__).parent / "targets" / "feedback_actor" / "scenarios"


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
}
