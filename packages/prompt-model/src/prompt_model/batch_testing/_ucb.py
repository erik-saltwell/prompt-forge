import math


class ArmStats:
    """Mutable per-arm UCB state.

    `pulls` is the number of completed pulls. `virtual_pulls` counts in-flight pulls and is bumped on
    dispatch / decremented on completion so concurrent UCB picks do not all pile onto the same arm.
    """

    __slots__ = ("pulls", "reward_sum", "virtual_pulls")

    def __init__(self) -> None:
        self.pulls: int = 0
        self.reward_sum: float = 0.0
        self.virtual_pulls: int = 0

    def record(self, reward: float) -> None:
        self.pulls += 1
        self.reward_sum += reward

    @property
    def mean(self) -> float:
        return self.reward_sum / self.pulls if self.pulls > 0 else 0.0

    @property
    def effective_pulls(self) -> int:
        return self.pulls + self.virtual_pulls


def ucb_score(stats: ArmStats, total_pulls: int, exploration_bonus: float) -> float:
    """UCB1 score with virtual-visit accounting for in-flight pulls."""
    effective: int = stats.effective_pulls
    if effective <= 0 or total_pulls <= 0:
        return math.inf
    return stats.mean + exploration_bonus * math.sqrt(math.log(max(total_pulls, 1)) / effective)


def pick_arm(arms: list[tuple[int, ArmStats]], total_pulls: int, exploration_bonus: float, rng_tiebreak: int = 0) -> int:
    """Pick the index of the arm with the highest UCB score.

    `arms` is a list of (arm_id, ArmStats); returns the chosen `arm_id`. Ties are broken by
    `rng_tiebreak` (deterministic — usually 0 — caller may pass a rotating value for fairness).
    """
    if not arms:
        raise ValueError("pick_arm requires at least one eligible arm")
    best_score: float = -math.inf
    best_arm: int = arms[0][0]
    for offset, (arm_id, stats) in enumerate(arms):
        score: float = ucb_score(stats, total_pulls, exploration_bonus)
        if score > best_score or (score == best_score and ((offset + rng_tiebreak) % len(arms) == 0)):
            best_score = score
            best_arm = arm_id
    return best_arm
