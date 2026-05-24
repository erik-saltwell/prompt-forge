from __future__ import annotations

import json

from prompt_model._actor._signal_rendering_strategy import (
    DefaultSignalRenderingStrategy,
    JsonSignalRenderingStrategy,
    XmlSignalRenderingStrategy,
)
from prompt_model._metrics._aggregator import AggregatedNodeBucket
from prompt_model._metrics.result import IssueSignal


def _signal(
    *,
    rationale: str = "rat",
    target_behavior: str = "tb",
    success_criterion: str = "sc",
    suggested_prompt_change: str | None = None,
    input_snippet: str = "in",
    output_snippet: str = "out",
    seen_in_n_cases: int = 1,
    culprit_node_id: str = "1.1",
) -> IssueSignal:
    return IssueSignal(
        culprit_node_id=culprit_node_id,
        rationale=rationale,
        target_behavior=target_behavior,
        success_criterion=success_criterion,
        suggested_prompt_change=suggested_prompt_change,
        input_snippet=input_snippet,
        output_snippet=output_snippet,
        seen_in_n_cases=seen_in_n_cases,
    )


def test_renders_culprit_node_id_in_header() -> None:
    bucket = AggregatedNodeBucket(culprit_node_id="1.2.3", signals=[_signal()])
    out: str = DefaultSignalRenderingStrategy().render(bucket)
    assert "`1.2.3`" in out


def test_renders_each_signal_as_numbered_subsection() -> None:
    bucket = AggregatedNodeBucket(
        culprit_node_id="1.1",
        signals=[_signal(rationale="a"), _signal(rationale="b"), _signal(rationale="c")],
    )
    out: str = DefaultSignalRenderingStrategy().render(bucket)
    assert "## Issue 1" in out
    assert "## Issue 2" in out
    assert "## Issue 3" in out


def test_renders_required_fields() -> None:
    bucket = AggregatedNodeBucket(
        culprit_node_id="1.1",
        signals=[_signal(rationale="R", target_behavior="TB", success_criterion="SC", input_snippet="IN", output_snippet="OUT")],
    )
    out: str = DefaultSignalRenderingStrategy().render(bucket)
    assert "R" in out
    assert "TB" in out
    assert "SC" in out
    assert "IN" in out
    assert "OUT" in out


def test_omits_suggested_change_when_absent() -> None:
    bucket = AggregatedNodeBucket(culprit_node_id="1.1", signals=[_signal(suggested_prompt_change=None)])
    out: str = DefaultSignalRenderingStrategy().render(bucket)
    assert "Suggested change" not in out


def test_includes_suggested_change_when_present() -> None:
    bucket = AggregatedNodeBucket(culprit_node_id="1.1", signals=[_signal(suggested_prompt_change="do X")])
    out: str = DefaultSignalRenderingStrategy().render(bucket)
    assert "Suggested change" in out
    assert "do X" in out


def test_shows_seen_in_n_cases_only_when_greater_than_one() -> None:
    bucket1 = AggregatedNodeBucket(culprit_node_id="1.1", signals=[_signal(seen_in_n_cases=1)])
    bucket_many = AggregatedNodeBucket(culprit_node_id="1.1", signals=[_signal(seen_in_n_cases=4)])
    assert "seen in" not in DefaultSignalRenderingStrategy().render(bucket1)
    assert "seen in 4 cases" in DefaultSignalRenderingStrategy().render(bucket_many)


# --- JsonSignalRenderingStrategy ---


def test_json_emits_valid_json_with_all_bucket_fields() -> None:
    bucket = AggregatedNodeBucket(
        culprit_node_id="1.2",
        signals=[_signal(rationale="r1"), _signal(rationale="r2", seen_in_n_cases=3)],
    )
    out: str = JsonSignalRenderingStrategy().render(bucket)
    data = json.loads(out)
    assert data["culprit_node_id"] == "1.2"
    assert len(data["signals"]) == 2
    assert data["signals"][0]["rationale"] == "r1"
    assert data["signals"][1]["seen_in_n_cases"] == 3


# --- XmlSignalRenderingStrategy ---


def test_xml_includes_culprit_node_id_and_signal_count() -> None:
    bucket = AggregatedNodeBucket(
        culprit_node_id="1.2.3",
        signals=[_signal(rationale="r1"), _signal(rationale="r2")],
    )
    out: str = XmlSignalRenderingStrategy().render(bucket)
    assert 'culprit_node_id="1.2.3"' in out
    assert out.count("<signal") == 2
    assert "<rationale>r1</rationale>" in out
    assert "<rationale>r2</rationale>" in out


def test_xml_escapes_text_content() -> None:
    bucket = AggregatedNodeBucket(
        culprit_node_id="1.1",
        signals=[_signal(rationale="a < b & c > d")],
    )
    out: str = XmlSignalRenderingStrategy().render(bucket)
    assert "a &lt; b &amp; c &gt; d" in out


def test_xml_omits_suggested_change_when_absent() -> None:
    bucket = AggregatedNodeBucket(culprit_node_id="1.1", signals=[_signal(suggested_prompt_change=None)])
    out: str = XmlSignalRenderingStrategy().render(bucket)
    assert "<suggested_prompt_change>" not in out


def test_xml_emits_seen_in_n_cases_as_attribute() -> None:
    bucket = AggregatedNodeBucket(culprit_node_id="1.1", signals=[_signal(seen_in_n_cases=7)])
    out: str = XmlSignalRenderingStrategy().render(bucket)
    assert 'seen_in_n_cases="7"' in out
