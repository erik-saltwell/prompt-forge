from __future__ import annotations

from ._structural_cleanup_implementations import AlwaysCleanup, CleanupOnMoveAction, CleanupOnStructuralAction, NeverCleanup
from .structural_cleanup_options import StructuralCleanupOption
from .structural_cleanup_protocol import StructuralCleanupDecisionProtocol


def make_structural_cleanup_decider(option: StructuralCleanupOption) -> StructuralCleanupDecisionProtocol:  # type: ignore[return]
    """Return a structural cleanup decision object for *option*."""

    match option:
        case StructuralCleanupOption.ALWAYS:
            return AlwaysCleanup()
        case StructuralCleanupOption.NEVER:
            return NeverCleanup()
        case StructuralCleanupOption.ON_STRUCTURAL_ACTIONS:
            return CleanupOnStructuralAction()
        case StructuralCleanupOption.ON_MOVE_ACTIONS:
            return CleanupOnMoveAction()
    raise ValueError(f"Unsupported structural cleanup strategy: {option!r}")
