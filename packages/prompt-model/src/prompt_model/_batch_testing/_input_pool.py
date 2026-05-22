import random


class InputPool:
    """Per-candidate "unused inputs" tracker. Samples input indices without replacement using a seeded RNG."""

    def __init__(self, num_inputs: int, rng: random.Random) -> None:
        self._remaining: list[int] = list(range(num_inputs))
        rng.shuffle(self._remaining)

    def has_remaining(self) -> bool:
        return bool(self._remaining)

    def remaining_count(self) -> int:
        return len(self._remaining)

    def take(self) -> int:
        if not self._remaining:
            raise ValueError("InputPool exhausted")
        return self._remaining.pop()
