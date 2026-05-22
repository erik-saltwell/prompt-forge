from __future__ import annotations

import random
from pathlib import Path

from prompt_model._actions import Action, parse_action
from prompt_model._actions.protocol import SkipReason

from ..utils import _short_hand as sh
from ..utils import random_actions as ra

_LOG_DIR = Path(__file__).parent / "assets"
_LOG_FILE = _LOG_DIR / "long_action_generation.log"


def test_one_random_action() -> None:
    rng = random.Random(54)
    shorthand = sh.generate_random_shorthand(50, 6, rng)
    tree = sh.doc_from_shorthand(shorthand)
    action_dict = ra.generate_random_action(tree, rng)
    if action_dict is None:
        return
    action_or_reason: Action | SkipReason = parse_action(action_dict)
    assert not isinstance(action_or_reason, SkipReason)
    action: Action = action_or_reason
    assert action.validate(tree) is None


# def test_random_action_generator_long() -> None:
#     _LOG_DIR.mkdir(parents=True, exist_ok=True)
#     with _LOG_FILE.open("w", buffering=1) as log:
#         for _ in range(10000):
#             seed = random.SystemRandom().randrange(2**30 + 7)
#             rng = random.Random(seed)
#             try:
#                 shorthand = sh.generate_random_shorthand(50, 6, rng)
#                 tree = sh.doc_from_shorthand(shorthand)
#                 action_dict = ra.generate_random_action(tree, rng)
#                 if action_dict is None:
#                     log.write(f"none seed={seed}\n")
#                     continue
#                 action_or_reason: Action | SkipReason = parse_action(action_dict)
#                 assert not isinstance(action_or_reason, SkipReason)
#                 action: Action = action_or_reason
#                 assert action.validate(tree) is None
#             except Exception:
#                 log.write(f"FAIL seed={seed}\n")
#                 raise
#             log.write(f"pass seed={seed}\n")
