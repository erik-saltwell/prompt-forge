from __future__ import annotations

from typing import NamedTuple

from .._metrics import MetricResult
from .._prompt import Document


class CandidateResult(NamedTuple):
    """One returned candidate from run_batch: the prompt and the flat list of
    every MetricResult produced for it across all successful pulls."""

    prompt: Document
    results: list[MetricResult]
