import math

from prompt_model._batch_testing._ucb import ArmStats, pick_arm, ucb_score


def test_unvisited_arm_has_infinite_score() -> None:
    stats: ArmStats = ArmStats()
    assert ucb_score(stats, total_pulls=10, exploration_bonus=1.0) == math.inf


def test_higher_mean_arm_wins_when_equal_pulls() -> None:
    a: ArmStats = ArmStats()
    a.record(0.9)
    a.record(0.9)
    b: ArmStats = ArmStats()
    b.record(0.1)
    b.record(0.1)
    chosen: int = pick_arm([(0, a), (1, b)], total_pulls=4, exploration_bonus=1.0)
    assert chosen == 0


def test_unvisited_arm_beats_pulled_arm() -> None:
    a: ArmStats = ArmStats()
    a.record(0.99)
    a.record(0.99)
    fresh: ArmStats = ArmStats()
    chosen: int = pick_arm([(0, a), (1, fresh)], total_pulls=2, exploration_bonus=1.0)
    assert chosen == 1


def test_virtual_pulls_deprioritize_in_flight_arm() -> None:
    a: ArmStats = ArmStats()
    a.record(0.5)
    a.virtual_pulls = 5  # arm has 5 in-flight pulls
    b: ArmStats = ArmStats()
    b.record(0.5)
    chosen: int = pick_arm([(0, a), (1, b)], total_pulls=6, exploration_bonus=2.0)
    assert chosen == 1
