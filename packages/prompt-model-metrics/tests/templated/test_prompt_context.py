from __future__ import annotations

import pytest
from prompt_model_metrics.templated import SCORE_MAX, SCORE_MIN, PromptContext, PromptContextDraft, ScoreRange, ScoringRubric


def test_normalize_score_min_maps_to_zero() -> None:
    ctx = PromptContext(criterion="c", evaluation_steps=["s"], scoring_rubric=[])
    assert ctx.normalize_score(SCORE_MIN) == 0.0


def test_normalize_score_max_maps_to_one() -> None:
    ctx = PromptContext(criterion="c")
    assert ctx.normalize_score(SCORE_MAX) == 1.0


def test_normalize_score_midpoint() -> None:
    ctx = PromptContext(criterion="c")
    assert ctx.normalize_score(3) == pytest.approx(0.5)


def test_normalize_score_real_valued() -> None:
    ctx = PromptContext(criterion="c")
    assert ctx.normalize_score(2.5) == pytest.approx(0.375)


def test_normalize_score_out_of_range_raises() -> None:
    ctx = PromptContext(criterion="c")
    with pytest.raises(ValueError):
        ctx.normalize_score(0)
    with pytest.raises(ValueError):
        ctx.normalize_score(6)


def test_draft_to_context_copies_fields() -> None:
    draft = PromptContextDraft(
        reasoning="because",
        evaluation_steps=["read it", "compare"],
        scoring_rubric=[ScoringRubric(score_range=ScoreRange(minimum=1, maximum=5), expected_outcome="varies")],
        requires_ground_truth=True,
    )
    ctx = draft.to_context("my criterion")
    assert ctx.criterion == "my criterion"
    assert ctx.evaluation_steps == ["read it", "compare"]
    assert len(ctx.scoring_rubric) == 1
    assert ctx.requires_ground_truth is True


def test_draft_requires_at_least_one_step() -> None:
    with pytest.raises(ValueError):
        PromptContextDraft(
            reasoning="r",
            evaluation_steps=[],
            scoring_rubric=[ScoringRubric(score_range=ScoreRange(minimum=1, maximum=5), expected_outcome="x")],
            requires_ground_truth=False,
        )


def test_draft_requires_at_least_one_rubric_band() -> None:
    with pytest.raises(ValueError):
        PromptContextDraft(
            reasoning="r",
            evaluation_steps=["s"],
            scoring_rubric=[],
            requires_ground_truth=False,
        )
