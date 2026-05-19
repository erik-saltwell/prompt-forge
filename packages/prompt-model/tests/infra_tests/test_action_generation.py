from __future__ import annotations

from pathlib import Path

from prompt_model._protocols import SkipReason
from prompt_model.service.actions import Action, parse_action

from ..utils import _short_hand as sh
from ..utils import random_actions as ra

_LOG_DIR = Path(__file__).parent / "assets"
_LOG_FILE = _LOG_DIR / "long_action_generation.log"


def test_one_random_action() -> None:
    seed: int = 54
    shorthand: str = sh.generate_random_shorthand(50, 6)
    tree = sh.doc_from_shorthand(shorthand)
    action_dict: dict | None = ra.generate_random_action(shorthand, seed + 1)
    if action_dict is None:
        return
    action_or_reason: Action | SkipReason = parse_action(action_dict)
    assert not isinstance(action_or_reason, SkipReason)
    action: Action = action_or_reason
    assert action.validate(tree) is None


# def test_random_action_generator_long() -> None:
#     seed: int = 53
#     _LOG_DIR.mkdir(parents=True, exist_ok=True)
#     with _LOG_FILE.open("w", buffering=1) as log:
#         for idx in range(10000):
#             shorthand: str = sh.generate_random_shorthand(50, 6)
#             try:
#                 tree = sh.doc_from_shorthand(shorthand)
#                 action_dict: dict | None = ra.generate_random_action(shorthand, seed + idx)
#                 if action_dict is None:
#                     log.write(f"none: shorthand={shorthand!r}:\n")
#                     continue
#                 action_or_reason: Action | SkipReason = parse_action(action_dict)
#                 assert not isinstance(action_or_reason, SkipReason)
#                 action: Action = action_or_reason
#                 assert action.validate(tree) is None
#             except Exception:
#                 log.write(f"FAIL: shorthand={shorthand!r}\n")
#                 raise
#             log.write(f"pass: shorthand={shorthand!r}:\n")
