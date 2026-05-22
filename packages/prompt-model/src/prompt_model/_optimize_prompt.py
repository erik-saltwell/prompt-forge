from ._batch_testing.reward import RewardStrategy
from ._metrics.protocol import Metric
from ._progress import ProgressReporter
from ._result import OptimizeResult
from .config import OptimizerConfig


async def optimize_prompt(
    config: OptimizerConfig,
    metrics: list[Metric],
    scorer: RewardStrategy,
    progress_reporter: ProgressReporter = None,
) -> OptimizeResult:
    """Optimize a prompt against a set of evaluation cases. See docs/public-facade.md."""
    raise NotImplementedError("optimize_prompt body not yet implemented")
