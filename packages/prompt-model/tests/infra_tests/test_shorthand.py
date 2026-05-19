from __future__ import annotations

import random
from pathlib import Path

from ..utils import _short_hand as sh
from ..utils import validation as val

_LOG_DIR = Path(__file__).parent / "assets"
_LOG_FILE = _LOG_DIR / "long_shorthand_generation.log"


def test_random_shorthand_generator_one() -> None:
    rng = random.Random(444)
    shorthand = sh.generate_random_shorthand(max_elements=20, max_depth=6, rng=rng)
    val.check_no_errors_from_md(sh.shorthand_to_markdown(shorthand))


# def test_random_shorthand_generator_long() -> None:
#     _LOG_DIR.mkdir(parents=True, exist_ok=True)
#     with _LOG_FILE.open("w", buffering=1) as log:
#         for _ in range(10000):
#             seed = random.SystemRandom().randrange(2**32)
#             rng = random.Random(seed)
#             try:
#                 shorthand = sh.generate_random_shorthand(max_elements=25, max_depth=6, rng=rng)
#                 val.check_no_errors_from_md(sh.shorthand_to_markdown(shorthand))
#             except Exception:
#                 log.write(f"FAIL seed={seed}\n")
#                 raise
#             log.write(f"pass seed={seed}\n")
