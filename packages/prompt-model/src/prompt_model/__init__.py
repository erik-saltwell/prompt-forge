import structlog

from ._metrics.base_llm_judge import BaseLLMJudgeMetric
from ._metrics.hybrid_metric import HybridMetric, JudgeDiagnosis
from ._metrics.protocol import Metric, MissingGroundTruthError
from ._metrics.result import IssueSignal, MetricResult
from ._optimize_prompt import optimize_prompt
from ._progress import ProgressEvent, ProgressReporter, RunProgress, StepProgress, TaskProgress
from ._result import CandidateSummary, OptimizationResult
from .reporting import render_report
from .strategies.prompt_rendering_strategy import RenderPromptOption
from .strategies.redaction_strategy import RedactionOption
from .strategies.signal_render_strategy import RenderSignalOption
from .strategies.structural_cleanup_strategy import StructuralCleanupOption

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
    "RedactionOption",
    "RenderPromptOption",
    "RenderSignalOption",
    "RunProgress",
    "StepProgress",
    "StructuralCleanupOption",
    "TaskProgress",
    "optimize_prompt",
    "render_report",
]
