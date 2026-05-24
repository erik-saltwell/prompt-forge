from __future__ import annotations

import asyncio
import time

import pytest
from prompt_model._candidate.candidate import Candidate
from prompt_model._critic.composite_scorer import MeanScorer
from prompt_model._critic.select_next_candidates import (
    TooManyEvaluationErrorsError,
    process_floor,
    process_ucb,
    select_top_candidates,
)
from prompt_model._critic.selection_data import _SelectionData
from prompt_model.config import LiteLLMConfig

from .conftest import FakeMetric, RecordingMetric, fake_acomplete_factory, make_candidate, make_cases, ok_result


def _patch_acomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("prompt_model._critic.candidate_evaluator.acomplete", fake_acomplete_factory())


def _cfg() -> LiteLLMConfig:
    return LiteLLMConfig(model="fake/model")


def _selections(*headings: str, case_count: int = 4) -> list[_SelectionData]:
    return [_SelectionData(make_candidate(h, case_count=case_count)) for h in headings]


# ---------------------------------------------------------------------------
# process_floor
# ---------------------------------------------------------------------------


def test_floor_runs_each_candidate_to_floor_size(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_acomplete(monkeypatch)
    sd_list: list[_SelectionData] = _selections("a", "b", case_count=5)
    metric: FakeMetric = FakeMetric([ok_result(0.5)] * 10)

    errors: int = asyncio.run(
        process_floor(
            candidates=sd_list,
            floor_size=2,
            inputs=make_cases(5),
            execution_config=_cfg(),
            metrics=[metric],  # type: ignore[list-item]
            scorer=MeanScorer(),
            max_errors=0,
        )
    )

    assert errors == 0
    for sd in sd_list:
        assert sd.completed_tests_this_run == 2


def test_floor_aborts_when_errors_exceed_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_acomplete(monkeypatch)
    sd_list: list[_SelectionData] = _selections("a", "b", case_count=4)
    metric: FakeMetric = FakeMetric([RuntimeError("boom")] * 10)

    with pytest.raises(TooManyEvaluationErrorsError):
        asyncio.run(
            process_floor(
                candidates=sd_list,
                floor_size=2,
                inputs=make_cases(4),
                execution_config=_cfg(),
                metrics=[metric],  # type: ignore[list-item]
                scorer=MeanScorer(),
                max_errors=1,
            )
        )


def test_floor_skips_candidate_that_runs_out_of_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_acomplete(monkeypatch)
    short: _SelectionData = _SelectionData(make_candidate("short", case_count=1))
    full: _SelectionData = _SelectionData(make_candidate("full", case_count=4))
    metric: FakeMetric = FakeMetric([ok_result(1.0)] * 10)

    asyncio.run(
        process_floor(
            candidates=[short, full],
            floor_size=2,
            inputs=make_cases(4),
            execution_config=_cfg(),
            metrics=[metric],  # type: ignore[list-item]
            scorer=MeanScorer(),
            max_errors=0,
        )
    )

    assert short.completed_tests_this_run == 1
    assert full.completed_tests_this_run == 2


# ---------------------------------------------------------------------------
# process_ucb
# ---------------------------------------------------------------------------


def test_ucb_runs_budget_pulls(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_acomplete(monkeypatch)
    sd_list: list[_SelectionData] = _selections("a", "b", case_count=10)
    for sd in sd_list:
        sd._completed_tests = 1
        sd._sum_of_scores = 0.5
    metric: FakeMetric = FakeMetric([ok_result(0.5)] * 10)

    asyncio.run(
        process_ucb(
            candidates=sd_list,
            ucb_budget=4,
            inputs=make_cases(10),
            execution_config=_cfg(),
            metrics=[metric],  # type: ignore[list-item]
            scorer=MeanScorer(),
            max_errors=0,
            error_count=0,
            exploration_bonus=1.0,
        )
    )

    total_pulls: int = sum(sd.completed_tests_this_run for sd in sd_list)
    assert total_pulls == 1 + 1 + 4


def test_ucb_stops_when_no_eligible_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_acomplete(monkeypatch)
    sd_list: list[_SelectionData] = _selections("a", case_count=4)
    metric: FakeMetric = FakeMetric([ok_result(1.0)] * 5)

    asyncio.run(
        process_ucb(
            candidates=sd_list,
            ucb_budget=4,
            inputs=make_cases(4),
            execution_config=_cfg(),
            metrics=[metric],  # type: ignore[list-item]
            scorer=MeanScorer(),
            max_errors=0,
            error_count=0,
            exploration_bonus=1.0,
        )
    )

    assert sd_list[0].completed_tests_this_run == 0


def test_ucb_retries_on_per_pull_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_acomplete(monkeypatch)
    sd_list: list[_SelectionData] = _selections("a", case_count=10)
    sd_list[0]._completed_tests = 1
    sd_list[0]._sum_of_scores = 0.5
    metric: FakeMetric = FakeMetric([RuntimeError("transient"), ok_result(1.0), ok_result(1.0), ok_result(1.0)])

    asyncio.run(
        process_ucb(
            candidates=sd_list,
            ucb_budget=3,
            inputs=make_cases(10),
            execution_config=_cfg(),
            metrics=[metric],  # type: ignore[list-item]
            scorer=MeanScorer(),
            max_errors=5,
            error_count=0,
            exploration_bonus=1.0,
        )
    )

    # Seeded with 1 prior completed pull + 3 successful ucb pulls = 4. The transient failure rolled back.
    assert sd_list[0].completed_tests_this_run == 4
    assert metric.calls == 4


def test_ucb_aborts_when_errors_exceed_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_acomplete(monkeypatch)
    sd_list: list[_SelectionData] = _selections("a", case_count=10)
    sd_list[0]._completed_tests = 1
    sd_list[0]._sum_of_scores = 0.5
    metric: FakeMetric = FakeMetric([RuntimeError("boom")] * 5)

    with pytest.raises(TooManyEvaluationErrorsError):
        asyncio.run(
            process_ucb(
                candidates=sd_list,
                ucb_budget=3,
                inputs=make_cases(10),
                execution_config=_cfg(),
                metrics=[metric],  # type: ignore[list-item]
                scorer=MeanScorer(),
                max_errors=1,
                error_count=0,
                exploration_bonus=1.0,
            )
        )


# ---------------------------------------------------------------------------
# select_top_candidates
# ---------------------------------------------------------------------------


def test_select_top_candidates_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_acomplete(monkeypatch)
    cands: list[Candidate] = [
        make_candidate("a", case_count=6),
        make_candidate("b", case_count=6),
    ]
    metric: FakeMetric = FakeMetric([ok_result(0.5)] * 20)

    out: list[Candidate] = asyncio.run(
        select_top_candidates(
            candidates=cands,
            inputs=make_cases(6),
            exploration_bonus=1.0,
            floor_size=2,
            ucb_budget=2,
            max_errors=0,
            execution_config=_cfg(),
            metrics=[metric],  # type: ignore[list-item]
            scorer=MeanScorer(),
        )
    )

    assert out == cands
    total_tested: int = sum(c.tested_count for c in out)
    assert total_tested == 6  # 2 candidates × 2 floor + 2 ucb pulls = 6


# ---------------------------------------------------------------------------
# Concurrency invariants (single test covering all four from the strategy doc)
# ---------------------------------------------------------------------------


def _intervals_overlap(a: tuple[str, float, float], b: tuple[str, float, float]) -> bool:
    return a[1] < b[2] and b[1] < a[2]


def test_concurrency_invariants(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the four invariants from docs/critic-async-strategy.md.

    1. A single _SelectionData is never evaluated more than once at the same time.
    2. Floor phase fans out across distinct candidates within a round.
    3. UCB starts only after floor phase has completed.
    4. UCB decisions are sequential.
    """
    intervals: list[tuple[str, float, float]] = []

    async def recording_acomplete(system_prompt: str, user_prompt: str, config: LiteLLMConfig) -> str:
        enter: float = time.monotonic()
        await asyncio.sleep(0.02)
        exit_: float = time.monotonic()
        intervals.append((system_prompt, enter, exit_))
        return "stub"

    monkeypatch.setattr("prompt_model._critic.candidate_evaluator.acomplete", recording_acomplete)

    cands: list[Candidate] = [
        make_candidate("alpha", case_count=4),
        make_candidate("beta", case_count=4),
        make_candidate("gamma", case_count=4),
    ]
    rec_metric: RecordingMetric = RecordingMetric(score=0.5, delay=0.0)

    asyncio.run(
        select_top_candidates(
            candidates=cands,
            inputs=make_cases(4),
            exploration_bonus=1.0,
            floor_size=2,
            ucb_budget=3,
            max_errors=0,
            execution_config=_cfg(),
            metrics=[rec_metric],  # type: ignore[list-item]
            scorer=MeanScorer(),
        )
    )

    # ----- Invariant 1: no two pulls for the same prompt overlap. -----
    by_prompt: dict[str, list[tuple[str, float, float]]] = {}
    for iv in intervals:
        by_prompt.setdefault(iv[0], []).append(iv)
    for prompt_text, ivs in by_prompt.items():
        for i in range(len(ivs)):
            for j in range(i + 1, len(ivs)):
                assert not _intervals_overlap(ivs[i], ivs[j]), f"overlap on {prompt_text!r}"

    # ----- Invariant 2: floor pulls fan out across candidates. -----
    first_pulls: list[tuple[str, float, float]] = [min(ivs, key=lambda iv: iv[1]) for ivs in by_prompt.values()]
    any_overlap: bool = any(_intervals_overlap(a, b) for i, a in enumerate(first_pulls) for b in first_pulls[i + 1 :])
    assert any_overlap, "expected floor-phase fan-out across candidates"

    # ----- Invariants 3 & 4: total floor pulls = 2 floor × 3 candidates = 6. UCB pulls = 3. -----
    total_pulls: int = sum(c.tested_count for c in cands)
    assert total_pulls == 6 + 3

    sorted_intervals: list[tuple[str, float, float]] = sorted(intervals, key=lambda iv: iv[1])
    ucb_pulls: list[tuple[str, float, float]] = sorted_intervals[6:9]
    for i, a in enumerate(ucb_pulls):
        for b in ucb_pulls[i + 1 :]:
            assert not _intervals_overlap(a, b), "ucb pulls must be sequential"

    floor_end: float = max(iv[2] for iv in sorted_intervals[:6])
    assert ucb_pulls[0][1] >= floor_end, "ucb must start only after floor completes"
