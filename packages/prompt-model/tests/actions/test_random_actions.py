# from __future__ import annotations

# import random
# from pathlib import Path

# from prompt_model._actions import Action, ApplyContext, SkipReason, parse_action

# from ..utils import _short_hand as sh
# from ..utils import actions as act
# from ..utils import random_actions as ra

# _LOG_DIR = Path(__file__).parent / "assets"
# _LOG_FILE = _LOG_DIR / "long_undo.log"


# def test_random_long_undo_sequences() -> None:
#     _LOG_DIR.mkdir(parents=True, exist_ok=True)
#     with _LOG_FILE.open("w", buffering=1) as log:
#         for _ in range(10000):
#             seed = random.SystemRandom().randrange(2**32)
#             rng = random.Random(seed)
#             try:
#                 shorthand = sh.generate_random_shorthand(30, 6, rng)
#                 tree = sh.doc_from_shorthand(shorthand)
#                 ctx = ApplyContext.from_tree(tree)
#                 actions: list[Action] = []
#                 for _ in range(rng.randint(1, 15)):
#                     action_dict = ra.generate_random_action(tree, rng)
#                     if action_dict is None:
#                         continue
#                     parsed = parse_action(action_dict)
#                     assert not isinstance(parsed, SkipReason)
#                     assert parsed.validate(tree) is None
#                     parsed.apply(tree, ctx)
#                     actions.append(parsed)
#                 act.check_undo_from_sh(shorthand, actions)
#             except BaseException:
#                 log.write(f"FAIL seed={seed}\n")
#                 raise
#             log.write(f"pass seed={seed}\n")
