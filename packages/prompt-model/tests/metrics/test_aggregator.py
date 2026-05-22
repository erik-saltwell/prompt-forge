from prompt_model.metrics import (
    DOCUMENT_SENTINEL,
    TOP_K_PER_BUCKET,
    AggregationResult,
    IssueSignal,
    MetricResult,
    aggregate,
)


def _signal(
    *,
    culprit_node_id: str = "1.2",
    success_criterion: str = "no example uses a casual register",
    rationale: str = "the example contradicts the rule",
    target_behavior: str = "examples match the stated tone",
    suggested_prompt_change: str | None = None,
    input_snippet: str = "Tell me a joke.",
    output_snippet: str = "Sure, here's one: ...",
) -> IssueSignal:
    return IssueSignal(
        culprit_node_id=culprit_node_id,
        rationale=rationale,
        target_behavior=target_behavior,
        success_criterion=success_criterion,
        suggested_prompt_change=suggested_prompt_change,
        input_snippet=input_snippet,
        output_snippet=output_snippet,
    )


def _result(*signals: IssueSignal, metric_name: str = "tone", preserve: list[str] | None = None) -> MetricResult:
    return MetricResult(
        metric_name=metric_name,
        score=0.5,
        assessment="ok",
        signals=list(signals),
        preserve=preserve or [],
    )


def test_empty_input_produces_empty_result() -> None:
    result: AggregationResult = aggregate([])
    assert result.buckets == []
    assert result.preserve == []


def test_single_signal_produces_one_bucket() -> None:
    result: AggregationResult = aggregate([_result(_signal())])
    assert len(result.buckets) == 1
    bucket = result.buckets[0]
    assert bucket.culprit_node_id == "1.2"
    assert len(bucket.signals) == 1
    assert bucket.signals[0].seen_in_n_cases == 1


def test_identical_signals_dedupe_with_count() -> None:
    s1: IssueSignal = _signal()
    s2: IssueSignal = _signal()
    result: AggregationResult = aggregate([_result(s1, s2)])
    assert len(result.buckets) == 1
    assert len(result.buckets[0].signals) == 1
    assert result.buckets[0].signals[0].seen_in_n_cases == 2


def test_same_culprit_different_success_criterion_kept_distinct() -> None:
    s1: IssueSignal = _signal(success_criterion="no casual register")
    s2: IssueSignal = _signal(success_criterion="examples are under 20 words")
    result: AggregationResult = aggregate([_result(s1, s2)])
    assert len(result.buckets) == 1
    assert len(result.buckets[0].signals) == 2


def test_different_culprits_produce_separate_buckets() -> None:
    s1: IssueSignal = _signal(culprit_node_id="1.2")
    s2: IssueSignal = _signal(culprit_node_id="3.4")
    result: AggregationResult = aggregate([_result(s1, s2)])
    assert {b.culprit_node_id for b in result.buckets} == {"1.2", "3.4"}


def test_document_sentinel_routes_to_its_own_bucket() -> None:
    s_doc: IssueSignal = _signal(culprit_node_id=DOCUMENT_SENTINEL)
    s_node: IssueSignal = _signal(culprit_node_id="1.2")
    result: AggregationResult = aggregate([_result(s_doc, s_node)])
    ids: set[str] = {b.culprit_node_id for b in result.buckets}
    assert ids == {DOCUMENT_SENTINEL, "1.2"}


def test_normalization_collapses_case_and_trailing_punct() -> None:
    s1: IssueSignal = _signal(success_criterion="Be concise")
    s2: IssueSignal = _signal(success_criterion="be concise.")
    result: AggregationResult = aggregate([_result(s1, s2)])
    assert len(result.buckets[0].signals) == 1
    assert result.buckets[0].signals[0].seen_in_n_cases == 2


def test_different_metric_names_do_not_dedupe() -> None:
    s1: IssueSignal = _signal()
    s2: IssueSignal = _signal()
    result: AggregationResult = aggregate([_result(s1, metric_name="tone"), _result(s2, metric_name="accuracy")])
    assert len(result.buckets[0].signals) == 2


def test_base_signal_prefers_one_with_suggested_prompt_change() -> None:
    s_no_suggestion: IssueSignal = _signal(rationale="version A", input_snippet="A in", output_snippet="A out")
    s_with_suggestion: IssueSignal = _signal(
        rationale="version B",
        input_snippet="B in",
        output_snippet="B out",
        suggested_prompt_change="rewrite the example formally",
    )
    result: AggregationResult = aggregate([_result(s_no_suggestion, s_with_suggestion)])
    merged: IssueSignal = result.buckets[0].signals[0]
    assert merged.suggested_prompt_change == "rewrite the example formally"
    assert merged.rationale == "version B"
    assert merged.input_snippet == "B in"
    assert merged.output_snippet == "B out"
    assert merged.seen_in_n_cases == 2


def test_base_signal_is_verbatim_no_field_mashup() -> None:
    s1: IssueSignal = _signal(rationale="rationale 1", input_snippet="in 1", output_snippet="out 1")
    s2: IssueSignal = _signal(rationale="rationale 2", input_snippet="in 2", output_snippet="out 2")
    result: AggregationResult = aggregate([_result(s1, s2)])
    merged: IssueSignal = result.buckets[0].signals[0]
    assert (merged.rationale, merged.input_snippet, merged.output_snippet) in {
        ("rationale 1", "in 1", "out 1"),
        ("rationale 2", "in 2", "out 2"),
    }


def test_top_k_cap_keeps_highest_counts() -> None:
    distinct_signals: list[IssueSignal] = [_signal(success_criterion=f"criterion {i}") for i in range(TOP_K_PER_BUCKET + 2)]
    inputs: list[MetricResult] = [_result(s) for s in distinct_signals]
    extra_dupes: list[MetricResult] = [_result(_signal(success_criterion="criterion 0")) for _ in range(5)]
    result: AggregationResult = aggregate(inputs + extra_dupes)
    bucket = result.buckets[0]
    assert len(bucket.signals) == TOP_K_PER_BUCKET
    assert bucket.signals[0].seen_in_n_cases == 6
    assert all(bucket.signals[i].seen_in_n_cases >= bucket.signals[i + 1].seen_in_n_cases for i in range(len(bucket.signals) - 1))


def test_preserve_is_global_deduped_union_in_first_seen_order() -> None:
    r1: MetricResult = _result(_signal(), preserve=["keep tone", "keep examples"])
    r2: MetricResult = _result(_signal(culprit_node_id="3.4"), metric_name="accuracy", preserve=["keep examples", "keep structure"])
    result: AggregationResult = aggregate([r1, r2])
    assert result.preserve == ["keep tone", "keep examples", "keep structure"]


def test_results_with_no_signals_skip_buckets_but_keep_preserve() -> None:
    clean: MetricResult = _result(preserve=["keep tone"])
    result: AggregationResult = aggregate([clean])
    assert result.buckets == []
    assert result.preserve == ["keep tone"]
