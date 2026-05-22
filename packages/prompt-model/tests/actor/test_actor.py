from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from prompt_model._actor import Actor, ActorResult
from prompt_model._metrics._aggregator import AggregatedNodeBucket, AggregationResult, IssueSignal
from prompt_model._prompt.parsing.parse_prompt import parse_from_string
from prompt_model.config import LiteLLMConfig


def _signal(node_id: str) -> IssueSignal:
    return IssueSignal(
        culprit_node_id=node_id,
        rationale="needs renaming",
        target_behavior="clearer heading",
        success_criterion="heading reads 'new'",
        input_snippet="x",
        output_snippet="y",
    )


def _llm_config() -> LiteLLMConfig:
    return LiteLLMConfig(model="anthropic/claude-haiku-4-5")


def _fake_llm_returning(payload: str) -> Callable[..., Awaitable[str]]:
    async def fake(*_args: Any, **_kwargs: Any) -> str:
        return payload

    return fake


def test_revise_single_bucket_applies_actions_and_returns_one_result(monkeypatch: pytest.MonkeyPatch) -> None:
    tree = parse_from_string("# old\n")
    aggregation = AggregationResult(
        buckets=[AggregatedNodeBucket(culprit_node_id="1", signals=[_signal("1")])],
        preserve=[],
    )

    payload = '{"reasoning": "rename heading", "actions": [{"action": "rewrite_node", "id": "1", "text": "new"}]}'
    monkeypatch.setattr("prompt_model._actor.actor.acomplete", _fake_llm_returning(payload))

    actor = Actor(_llm_config())
    results: list[ActorResult] = asyncio.run(actor.revise(tree, aggregation))

    assert len(results) == 1
    assert results[0].document.to_markdown() == "# new\n"
    assert results[0].applied == [0]
    assert results[0].skipped == []


def test_revise_drops_bucket_when_llm_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    tree = parse_from_string("# old\n")
    aggregation = AggregationResult(
        buckets=[AggregatedNodeBucket(culprit_node_id="1", signals=[_signal("1")])],
        preserve=[],
    )

    async def boom(*_args: Any, **_kwargs: Any) -> str:
        raise RuntimeError("transport failure")

    monkeypatch.setattr("prompt_model._actor.actor.acomplete", boom)

    actor = Actor(_llm_config())
    results: list[ActorResult] = asyncio.run(actor.revise(tree, aggregation))

    assert results == []


def test_revise_drops_bucket_when_actor_returns_empty_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    tree = parse_from_string("# old\n")
    aggregation = AggregationResult(
        buckets=[AggregatedNodeBucket(culprit_node_id="1", signals=[_signal("1")])],
        preserve=[],
    )

    payload = '{"reasoning": "no edits needed", "actions": []}'
    monkeypatch.setattr("prompt_model._actor.actor.acomplete", _fake_llm_returning(payload))

    actor = Actor(_llm_config())
    results: list[ActorResult] = asyncio.run(actor.revise(tree, aggregation))

    assert results == []


def test_revise_fans_out_one_result_per_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    tree = parse_from_string("# alpha\n\n# beta\n")
    aggregation = AggregationResult(
        buckets=[
            AggregatedNodeBucket(culprit_node_id="1", signals=[_signal("1")]),
            AggregatedNodeBucket(culprit_node_id="2", signals=[_signal("2")]),
        ],
        preserve=[],
    )

    async def fake(_config: Any, messages: list[dict[str, str]]) -> str:
        body = messages[0]["content"]
        if '"culprit_node_id":"1"' in body:
            return '{"reasoning": "r1", "actions": [{"action": "rewrite_node", "id": "1", "text": "A"}]}'
        return '{"reasoning": "r2", "actions": [{"action": "rewrite_node", "id": "2", "text": "B"}]}'

    monkeypatch.setattr("prompt_model._actor.actor.acomplete", fake)

    actor = Actor(_llm_config())
    results: list[ActorResult] = asyncio.run(actor.revise(tree, aggregation))

    assert len(results) == 2
    rendered = {r.document.to_markdown() for r in results}
    assert rendered == {"# A\n\n# beta\n", "# alpha\n\n# B\n"}


def test_revise_passes_preserve_list_to_every_bucket_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    tree = parse_from_string("# alpha\n\n# beta\n")
    aggregation = AggregationResult(
        buckets=[
            AggregatedNodeBucket(culprit_node_id="1", signals=[_signal("1")]),
            AggregatedNodeBucket(culprit_node_id="2", signals=[_signal("2")]),
        ],
        preserve=["keep the warm tone", "keep the closing line"],
    )

    seen_bodies: list[str] = []

    async def capture(_config: Any, messages: list[dict[str, str]]) -> str:
        seen_bodies.append(messages[0]["content"])
        return '{"reasoning": "noop", "actions": [{"action": "rewrite_node", "id": "1", "text": "x"}]}'

    monkeypatch.setattr("prompt_model._actor.actor.acomplete", capture)

    actor = Actor(_llm_config())
    asyncio.run(actor.revise(tree, aggregation))

    assert len(seen_bodies) == 2
    for body in seen_bodies:
        assert "keep the warm tone" in body
        assert "keep the closing line" in body


def test_revise_empty_aggregation_returns_empty_list() -> None:
    tree = parse_from_string("# foo\n")
    aggregation = AggregationResult(buckets=[], preserve=[])

    actor = Actor(_llm_config())
    results: list[ActorResult] = asyncio.run(actor.revise(tree, aggregation))

    assert results == []
