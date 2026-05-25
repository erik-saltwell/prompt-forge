import structlog

from ._metrics.base_llm_judge import BaseLLMJudgeMetric
from ._metrics.hybrid_metric import HybridMetric, JudgeDiagnosis
from ._metrics.protocol import Metric, MissingGroundTruthError
from ._metrics.result import IssueSignal, MetricResult
from ._optimize_prompt import optimize_prompt
from ._progress import ProgressEvent, ProgressReporter, RunProgress, StepProgress, TaskProgress
from ._result import CandidateSummary, OptimizationResult
from .reporting import render_report

# Silent default: until a caller calls tracing.initialize_tracing(...) or otherwise
# configures structlog, all log calls in prompt_model become no-ops. Keeps test runs
# clean and library code zero-impact when unconfigured.
if not structlog.is_configured():
    structlog.configure(logger_factory=structlog.ReturnLoggerFactory(), processors=[])

__all__ = [
    "BaseLLMJudgeMetric",
    "CandidateSummary",
    "HybridMetric",
    "IssueSignal",
    "JudgeDiagnosis",
    "Metric",
    "MetricResult",
    "MissingGroundTruthError",
    "OptimizationResult",
    "ProgressEvent",
    "ProgressReporter",
    "RunProgress",
    "StepProgress",
    "TaskProgress",
    "optimize_prompt",
    "render_report",
]
