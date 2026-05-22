import re

from pydantic import BaseModel, Field

from .result import IssueSignal, MetricResult

DOCUMENT_SENTINEL: str = "document"
TOP_K_PER_BUCKET: int = 10

_WHITESPACE_RE: re.Pattern[str] = re.compile(r"\s+")
_TRAILING_PUNCT: str = ".,;:!?"


class AggregatedNodeBucket(BaseModel):
    culprit_node_id: str = Field(
        description="The node id (or 'document' sentinel) all signals in this bucket accuse.",
    )
    signals: list[IssueSignal] = Field(
        description="Deduped signals for this node, capped at TOP_K_PER_BUCKET, ordered by seen_in_n_cases desc.",
    )


class AggregationResult(BaseModel):
    buckets: list[AggregatedNodeBucket] = Field(
        default_factory=list,
        description="One bucket per culprit node id that received at least one signal. Empty when the candidate is clean.",
    )
    preserve: list[str] = Field(
        default_factory=list,
        description="Deduped union of all MetricResult.preserve entries, in first-seen order.",
    )


def _normalize(s: str) -> str:
    collapsed: str = _WHITESPACE_RE.sub(" ", s).strip().lower()
    return collapsed.rstrip(_TRAILING_PUNCT)


def aggregate(results: list[MetricResult]) -> AggregationResult:
    """Convert per-(metric, case) MetricResults into per-node aggregated buckets.

    Each entry's `metric_name` participates in the dedupe key but is never written into the output —
    see docs/metric-aggregation.md.
    """
    grouped: dict[str, list[tuple[str, IssueSignal]]] = {}
    preserve_seen: dict[str, None] = {}

    for result in results:
        for entry in result.preserve:
            if entry not in preserve_seen:
                preserve_seen[entry] = None
        for signal in result.signals:
            grouped.setdefault(signal.culprit_node_id, []).append((result.metric_name, signal))

    buckets: list[AggregatedNodeBucket] = []
    for culprit_node_id, pairs in grouped.items():
        bucket_signals: list[IssueSignal] = _dedupe_bucket(culprit_node_id, pairs)
        if not bucket_signals:
            continue
        buckets.append(AggregatedNodeBucket(culprit_node_id=culprit_node_id, signals=bucket_signals))

    return AggregationResult(buckets=buckets, preserve=list(preserve_seen.keys()))


def _dedupe_bucket(culprit_node_id: str, pairs: list[tuple[str, IssueSignal]]) -> list[IssueSignal]:
    classes: dict[tuple[str, str, str], list[tuple[str, IssueSignal]]] = {}
    class_order: list[tuple[str, str, str]] = []

    for metric_name, signal in pairs:
        key: tuple[str, str, str] = (
            _normalize(metric_name),
            _normalize(culprit_node_id),
            _normalize(signal.success_criterion),
        )
        if key not in classes:
            classes[key] = []
            class_order.append(key)
        classes[key].append((metric_name, signal))

    merged: list[tuple[str, IssueSignal]] = []
    for key in class_order:
        members: list[tuple[str, IssueSignal]] = classes[key]
        base_metric_name, base_signal = _pick_base(members)
        merged_signal: IssueSignal = base_signal.model_copy(update={"seen_in_n_cases": len(members)})
        merged.append((base_metric_name, merged_signal))

    merged.sort(key=lambda pair: (-pair[1].seen_in_n_cases, pair[0]))
    capped: list[tuple[str, IssueSignal]] = merged[:TOP_K_PER_BUCKET]
    return [signal for _, signal in capped]


def _pick_base(members: list[tuple[str, IssueSignal]]) -> tuple[str, IssueSignal]:
    for metric_name, signal in members:
        if signal.suggested_prompt_change is not None:
            return metric_name, signal
    return members[0]
