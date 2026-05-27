"""Factory functions that build `PromptContext` values.

Three sources for a reusable `PromptContext`:

- `prompt_context_from_llm` — call the factory LLM to draft a `PromptContext` from a free-form
  criterion (uses the LRU cache in `_ai_prompt_factory`).
- `prompt_context_from_yaml` — load a pre-authored `PromptContext` from a YAML file on disk.
- `prompt_context_from_json` — load a pre-authored `PromptContext` from a JSON file on disk.

`prompts_from_llm` is a batch variant of `prompt_context_from_llm` that drafts many contexts
concurrently from a list of criteria.

The on-disk forms validate through pydantic, so they accept exactly the field set defined
on `PromptContext` (including the optional `definitions` and `important_reminders`).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import yaml
from prompt_model.config import LiteLLMConfig

from ._ai_prompt_factory import _create_prompt_context
from ._prompt_context import PromptContext


async def prompt_context_from_llm(
    criterion: str,
    factory_llm_config: LiteLLMConfig,
) -> PromptContext:
    """Build a `PromptContext` by having `factory_llm_config` draft it from `criterion`."""
    context: PromptContext = await _create_prompt_context(criterion, factory_llm_config)
    return context


def prompt_context_from_yaml(
    path: Path,
) -> PromptContext:
    """Load a `PromptContext` from a YAML file at `path`."""
    raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    context: PromptContext = PromptContext.model_validate(raw)
    return context


def prompt_context_from_json(
    path: Path,
) -> PromptContext:
    """Load a `PromptContext` from a JSON file at `path`."""
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    context: PromptContext = PromptContext.model_validate(raw)
    return context


async def prompts_from_llm(
    criteria: list[str],
    factory_llm_config: LiteLLMConfig,
) -> list[PromptContext]:
    """Draft one `PromptContext` per criterion concurrently via the factory LLM.

    Thin batch wrapper around `prompt_context_from_llm`. Results come back in the same
    order as `criteria`. Cache hits in `_ai_prompt_factory` are reused, so repeated
    criteria within one call are deduplicated for free.
    """
    return list(
        await asyncio.gather(
            *(
                prompt_context_from_llm(
                    criterion,
                    factory_llm_config,
                )
                for criterion in criteria
            )
        )
    )
