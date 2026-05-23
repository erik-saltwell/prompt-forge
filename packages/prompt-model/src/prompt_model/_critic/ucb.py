from __future__ import annotations

from .._candidate import Candidate
from .._metrics import EvalCase
from .candidate_picker import pick_next


def select_top_candidates(
    candidates: list[Candidate],
    inputs: list[EvalCase],
    max_candidate_count: int,
    exploration_bonus: float,
    floor_size: int,
    ucb_budget: int,
) -> list[Candidate] | None:
    for candidate in candidates:
        candidate.reset_for_ucb()
    total_pulls: int = (floor_size * len(candidates)) + ucb_budget
    for _idx in range(total_pulls):
        candidate: Candidate | None = pick_next(candidates=candidates, floor_size=floor_size, exploration_bonus=exploration_bonus)

    raise NotImplementedError()
