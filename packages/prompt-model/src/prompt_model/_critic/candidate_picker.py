from __future__ import annotations

from .selection_data import _SelectionData


def pick_next_ucb(candidates: list[_SelectionData], exploration_bonus: float) -> _SelectionData | None:
    eligible: list[_SelectionData] = [c for c in candidates if c.has_cases and c.completed_tests > 0]
    if not eligible:
        return None
    total_tests = sum(c.completed_tests for c in candidates)
    selected: _SelectionData = max(eligible, key=lambda c: c.ucb_score(exploration_bonus, total_tests))
    return selected
