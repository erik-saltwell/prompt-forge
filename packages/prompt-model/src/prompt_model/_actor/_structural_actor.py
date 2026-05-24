from __future__ import annotations

from pydantic import ValidationError

from .._actions.apply_batch import AppliedReport, apply_batch
from .._actions.inputs import ActionBatch
from .._llm import acomplete
from .._prompt import Document
from ..config import LiteLLMConfig
from ._render_prompt_strategy import RenderPromptStrategy
from ._resources import load_prompt


def _build_user_prompt(rendered_tree: str, preserve: list[str]) -> str:
    preserve_block: str = "\n".join(f"- {p}" for p in preserve) if preserve else "(none)"
    return f"<prompt>\n{rendered_tree}\n</prompt>\n\n<preserve>\n{preserve_block}\n</preserve>"


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
        )
    except ValidationError:
        return tree
    report: AppliedReport = apply_batch(tree, batch)
    if not report.applied:
        return tree
    return report.document
