from __future__ import annotations

import asyncio

from .._actions.apply_batch import apply_batch
from .._actions.inputs import ActionBatch
from .._llm.call import acomplete
from .._metrics._aggregator import AggregatedNodeBucket, AggregationResult
from .._prompt import Document
from ..config import LiteLLMConfig
from ._redaction import DefaultRedactionStrategy, RedactionStrategy
from ._result import ActorResult


class Actor:
    """Turns a tree + aggregation into up to g revised candidate documents.

    One actor LLM call per bucket; results are siblings of the parent tree.
    Failures (LLM error, empty action list) are dropped from the returned list.
    """

    def __init__(
        self,
        llm_config: LiteLLMConfig,
        redaction_strategy: RedactionStrategy | None = None,
        max_concurrent: int = 8,
    ) -> None:
        self._llm_config: LiteLLMConfig = llm_config
        self._redaction: RedactionStrategy = redaction_strategy or DefaultRedactionStrategy()
        self._sem: asyncio.Semaphore = asyncio.Semaphore(max_concurrent)

    async def revise(self, tree: Document, aggregation: AggregationResult) -> list[ActorResult]:
        tasks: list[asyncio.Task[ActorResult | None]] = [
            asyncio.create_task(self._revise_one(tree, bucket, aggregation.preserve)) for bucket in aggregation.buckets
        ]
        outcomes: list[ActorResult | None] = await asyncio.gather(*tasks)
        return [r for r in outcomes if r is not None]

    async def _revise_one(self, tree: Document, bucket: AggregatedNodeBucket, preserve: list[str]) -> ActorResult | None:
        system_prompt, user_prompt = self._build_prompts(tree, bucket, preserve)
        async with self._sem:
            try:
                response: str = await acomplete(system_prompt, user_prompt, self._llm_config)
            except Exception:
                return None
        batch: ActionBatch = ActionBatch.model_validate_json(response)
        if not batch.actions:
            return None
        report = apply_batch(tree, batch)
        return ActorResult(document=report.document, batch=batch, applied=report.applied, skipped=report.skipped)

    def _build_prompts(self, tree: Document, bucket: AggregatedNodeBucket, preserve: list[str]) -> tuple[str, str]:
        rendered: str = self._redaction.render(tree, bucket.culprit_node_id)
        preserve_block: str = "\n".join(f"- {p}" for p in preserve) if preserve else "(none)"
        user: str = (
            f"<prompt>\n{rendered}\n</prompt>\n<feedback>{bucket.model_dump_json()}</feedback>\n<preserve>\n{preserve_block}\n</preserve>"
        )
        return "", user
