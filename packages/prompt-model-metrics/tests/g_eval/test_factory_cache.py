from __future__ import annotations

import asyncio

import pytest
from prompt_model.config import LiteLLMConfig
from prompt_model_metrics.g_eval import (
    PromptContext,
    PromptContextDraft,
    ScoreRange,
    ScoringRubric,
    _ai_prompt_factory,
    create_prompt_context,
    reset_cache,
)


def _draft() -> PromptContextDraft:
    return PromptContextDraft(
        reasoning="r",
        evaluation_steps=["read", "compare"],
        scoring_rubric=[ScoringRubric(score_range=ScoreRange(1, 5), expected_outcome="band")],
        requires_ground_truth=False,
    )


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    reset_cache()


def test_cache_hit_skips_llm_call(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count: int = 0

    async def stub(system_prompt, user_prompt, config, *, response_format, log_name=None):
        nonlocal call_count
        call_count += 1
        return _draft()

    monkeypatch.setattr(_ai_prompt_factory, "acomplete", stub)
    cfg = LiteLLMConfig(model="fake/m")

    ctx1: PromptContext = asyncio.run(create_prompt_context("c1", cfg))
    ctx2: PromptContext = asyncio.run(create_prompt_context("c1", cfg))

    assert call_count == 1
    assert ctx1.criterion == "c1"
    assert ctx2 is ctx1


def test_different_criteria_invoke_separate_llm_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count: int = 0

    async def stub(system_prompt, user_prompt, config, *, response_format, log_name=None):
        nonlocal call_count
        call_count += 1
        return _draft()

    monkeypatch.setattr(_ai_prompt_factory, "acomplete", stub)
    cfg = LiteLLMConfig(model="fake/m")

    asyncio.run(create_prompt_context("c1", cfg))
    asyncio.run(create_prompt_context("c2", cfg))
    assert call_count == 2


def test_different_models_invoke_separate_llm_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count: int = 0

    async def stub(system_prompt, user_prompt, config, *, response_format, log_name=None):
        nonlocal call_count
        call_count += 1
        return _draft()

    monkeypatch.setattr(_ai_prompt_factory, "acomplete", stub)

    asyncio.run(create_prompt_context("c1", LiteLLMConfig(model="fake/m1")))
    asyncio.run(create_prompt_context("c1", LiteLLMConfig(model="fake/m2")))
    assert call_count == 2


def test_draft_promoted_to_context(monkeypatch: pytest.MonkeyPatch) -> None:
    async def stub(system_prompt, user_prompt, config, *, response_format, log_name=None):
        return PromptContextDraft(
            reasoning="r",
            evaluation_steps=["s"],
            scoring_rubric=[ScoringRubric(score_range=ScoreRange(1, 5), expected_outcome="x")],
            requires_ground_truth=True,
        )

    monkeypatch.setattr(_ai_prompt_factory, "acomplete", stub)
    cfg = LiteLLMConfig(model="fake/m")

    ctx: PromptContext = asyncio.run(create_prompt_context("ref-criterion", cfg))
    assert ctx.criterion == "ref-criterion"
    assert ctx.requires_ground_truth is True
    assert ctx.evaluation_steps == ["s"]
