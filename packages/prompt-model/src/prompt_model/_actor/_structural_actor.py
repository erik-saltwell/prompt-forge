from __future__ import annotations

import structlog
from pydantic import ValidationError

from .._actions.apply_batch import AppliedReport, apply_batch
from .._actions.inputs import ActionBatch
from .._llm import acomplete
from .._prompt import Document
from ..config import LiteLLMConfig
from ._render_prompt_strategy import RenderPromptStrategy
from ._resources import load_prompt

_log = structlog.get_logger()


def _build_user_prompt(rendered_tree: str, preserve: list[str]) -> str:
    preserve_block: str = "\n".join(f"- {p}" for p in preserve) if preserve else "(none)"
    return f"<prompt>\n{rendered_tree}\n</prompt>\n\n<preserve>\n{preserve_block}\n</preserve>"


def _emit_action_events(batch: ActionBatch, report: AppliedReport) -> None:
    skip_by_index: dict[int, str] = {s.index: str(s.reason) for s in report.skipped}
    for i, action_input in enumerate(batch.actions):
        _log.info(
            "action",
            actor_kind="structural",
            action_type=action_input.action,
            applied=(i in report.applied),
            skip_reason=skip_by_index.get(i),
        )


async def _cleanup_structure(
    tree: Document,
    preserve: list[str],
    llm_config: LiteLLMConfig,
    prompt_renderer: RenderPromptStrategy,
) -> Document:
    rendered_tree: str = prompt_renderer.render(tree, None)
    user_prompt: str = _build_user_prompt(rendered_tree, preserve)
    system_prompt: str = load_prompt("structural_actor")
    try:
        batch: ActionBatch = await acomplete(
            system_prompt,
            user_prompt,
            llm_config,
            response_format=ActionBatch,
            log_name="structural_actor",
        )
    except ValidationError:
        return tree
    report: AppliedReport = apply_batch(tree, batch)
    _emit_action_events(batch, report)
    if not report.applied:
        return tree
    return report.document
