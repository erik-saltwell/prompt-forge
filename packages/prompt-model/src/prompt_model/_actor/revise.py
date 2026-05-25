from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import NamedTuple

from pydantic import ValidationError

from .._actions.apply_batch import AppliedReport, apply_batch
from .._actions.inputs import ActionBatch
from .._candidate.candidate import Candidate
from .._llm import acomplete
from .._metrics._aggregator import AggregatedNodeBucket, AggregationResult, aggregate
from .._prompt import Document
from ..config import LiteLLMConfig
from ._redaction import DefaultRedactionStrategy, RedactionStrategy
from ._render_prompt_strategy import RenderPromptStrategy, XmlRenderPromptStrategy
from ._resources import load_prompt
from ._signal_rendering_strategy import DefaultSignalRenderingStrategy, SignalRenderingStrategy
from ._structural_actor import _cleanup_structure
from ._structural_strategy import always_cleanup_structure

_DEFAULT_REDACTION: RedactionStrategy = DefaultRedactionStrategy()
_DEFAULT_SIGNAL_RENDERER: SignalRenderingStrategy = DefaultSignalRenderingStrategy()
_DEFAULT_PROMPT_RENDERER: RenderPromptStrategy = XmlRenderPromptStrategy()


type StructuralCleanupPredicate = Callable[[ActionBatch], bool]


class PromptAndActions(NamedTuple):
    actions: ActionBatch
    prompt: Document


def _build_user_prompt(rendered_tree: str, rendered_signals: str, preserve: list[str]) -> str:
    preserve_block: str = "\n".join(f"- {p}" for p in preserve) if preserve else "(none)"
    return (
        f"<prompt>\n{rendered_tree}\n</prompt>\n\n<feedback>\n{rendered_signals}\n</feedback>\n\n<preserve>\n{preserve_block}\n</preserve>"
    )


async def _process_feedback(
    tree: Document,
    bucket: AggregatedNodeBucket,
    preserve: list[str],
    llm_config: LiteLLMConfig,
    prompt_redactor: RedactionStrategy,
    prompt_renderer: RenderPromptStrategy,
    signal_renderer: SignalRenderingStrategy,
) -> PromptAndActions | None:
    focus_ids: set[str] | None = prompt_redactor.focus_ids(tree, bucket.culprit_node_id)
    rendered_tree: str = prompt_renderer.render(tree, focus_ids)
    rendered_signals: str = signal_renderer.render(bucket)
    user_prompt: str = _build_user_prompt(rendered_tree, rendered_signals, preserve)
    system_prompt: str = load_prompt("feedback_actor")
    try:
        batch: ActionBatch = await acomplete(
            system_prompt,
            user_prompt,
            llm_config,
            response_format=ActionBatch,
        )
    except ValidationError:
        return None
    report: AppliedReport = apply_batch(tree, batch)
    if not report.applied:
        return None
    return PromptAndActions(actions=batch, prompt=report.document)


async def _process_bucket(
    tree: Document,
    bucket: AggregatedNodeBucket,
    preserve: list[str],
    feedback_llm_config: LiteLLMConfig,
    structural_llm_config: LiteLLMConfig | None,
    prompt_redactor: RedactionStrategy,
    prompt_renderer: RenderPromptStrategy,
    signal_renderer: SignalRenderingStrategy,
    should_run_structural_cleanup: StructuralCleanupPredicate,
    sem: asyncio.Semaphore,
) -> Document | None:
    async with sem:
        per_node: PromptAndActions | None = await _process_feedback(
            tree=tree,
            bucket=bucket,
            preserve=preserve,
            llm_config=feedback_llm_config,
            prompt_redactor=prompt_redactor,
            prompt_renderer=prompt_renderer,
            signal_renderer=signal_renderer,
        )
    if per_node is None:
        return None
    if not should_run_structural_cleanup(per_node.actions):
        return per_node.prompt
    structural_config: LiteLLMConfig = structural_llm_config if structural_llm_config is not None else feedback_llm_config
    async with sem:
        return await _cleanup_structure(
            tree=per_node.prompt,
            preserve=preserve,
            llm_config=structural_config,
            prompt_renderer=prompt_renderer,
        )


async def revise(
    candidate: Candidate,
    feedback_llm_config: LiteLLMConfig,
    structural_llm_config: LiteLLMConfig | None = None,
    max_concurrent: int = 8,
    max_children: int | None = None,
    redaction_strategy: RedactionStrategy | None = None,
    prompt_render_strategy: RenderPromptStrategy | None = None,
    signal_rendering_strategy: SignalRenderingStrategy | None = None,
    structural_cleanup_predicate: StructuralCleanupPredicate | None = None,
) -> list[Document]:
    if not candidate.results:
        return []
    aggregated_results: AggregationResult = aggregate(candidate.results)
    buckets: list[AggregatedNodeBucket] = aggregated_results.buckets
    if not buckets:
        return []

    if max_children is not None and len(buckets) > max_children:
        buckets = sorted(buckets, key=lambda b: sum(s.seen_in_n_cases for s in b.signals), reverse=True)[:max_children]

    prompt_redactor: RedactionStrategy = redaction_strategy if redaction_strategy is not None else _DEFAULT_REDACTION
    prompt_renderer: RenderPromptStrategy = prompt_render_strategy if prompt_render_strategy is not None else _DEFAULT_PROMPT_RENDERER
    signal_renderer: SignalRenderingStrategy = (
        signal_rendering_strategy if signal_rendering_strategy is not None else _DEFAULT_SIGNAL_RENDERER
    )
    should_run_structural_cleanup: StructuralCleanupPredicate = (
        structural_cleanup_predicate if structural_cleanup_predicate is not None else always_cleanup_structure
    )

    sem: asyncio.Semaphore = asyncio.Semaphore(max_concurrent)
    coroutines = [
        _process_bucket(
            tree=candidate.prompt,
            bucket=bucket,
            preserve=aggregated_results.preserve,
            feedback_llm_config=feedback_llm_config,
            structural_llm_config=structural_llm_config,
            prompt_redactor=prompt_redactor,
            prompt_renderer=prompt_renderer,
            signal_renderer=signal_renderer,
            should_run_structural_cleanup=should_run_structural_cleanup,
            sem=sem,
        )
        for bucket in buckets
    ]
    outcomes: list[Document | None] = await asyncio.gather(*coroutines)
    return [doc for doc in outcomes if doc is not None]
