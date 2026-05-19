from __future__ import annotations

from pathlib import Path

from ..utils import _short_hand as sh
from ..utils import validation as val

_LOG_DIR = Path(__file__).parent / "assets"
_LOG_FILE = _LOG_DIR / "long_shorthand_generation.log"


def test_random_shorthand_generator_one() -> None:
    shorthand: str = sh.generate_random_shorthand(max_elements=20, max_depth=6, seed=444)
    val.check_no_errors_from_md(sh.shorthand_to_markdown(shorthand))


# def test_random_shorthand_generator_long() -> None:
#     seed: int = 53
#     _LOG_DIR.mkdir(parents=True, exist_ok=True)
#     with _LOG_FILE.open("w", buffering=1) as log:
#         for idx in range(1000):
#             shorthand: str = sh.generate_random_shorthand(max_elements=25, max_depth=6, seed=seed + idx)
#             try:
#                 val.check_no_errors_from_md(sh.shorthand_to_markdown(shorthand))
#             except Exception:
#                 log.write(f"FAIL: shorthand={shorthand!r}\n")
#                 raise
#             log.write(f"pass: shorthand={shorthand!r}:\n")
