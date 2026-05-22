from typing import NamedTuple

from ..metrics import MetricResult
from ..prompt import Document


class CandidateResult(NamedTuple):
    """One returned candidate from `run_batch`: the prompt and the flat list of every MetricResult produced for it."""

    prompt: Document
    results: list[MetricResult]
