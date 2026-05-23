from __future__ import annotations

from .._candidate import Candidate


def pick_next(candidates: list[Candidate], floor_size: int, exploration_bonus: float) -> Candidate | None:
    eligible: list[Candidate] = [c for c in candidates if c.has_cases]
    if not eligible:
        return None
    candidates_below_floor: list[Candidate] = [c for c in eligible if c.effective_pulls < floor_size]
    if candidates_below_floor:
        return candidates_below_floor[0]
    total_tests: int = sum(c.effective_pulls for c in eligible)
    return max(eligible, key=lambda c: c.ucb_score(exploration_bonus, total_tests))
