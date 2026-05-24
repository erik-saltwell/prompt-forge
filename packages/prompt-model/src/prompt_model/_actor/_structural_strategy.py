from __future__ import annotations

from .._actions.inputs import ActionBatch

_STRUCTURAL_ACTIONS: frozenset[str] = frozenset({"insert_node", "delete_node", "move_node"})
_MOVE_ACTIONS: frozenset[str] = frozenset({"move_node"})


def always_cleanup_structure(batch: ActionBatch) -> bool:
    return True


def never_cleanup_structure(batch: ActionBatch) -> bool:
    return False


def cleanup_structure_on_structural_actions(batch: ActionBatch) -> bool:
    """Run the structural cleanup pass if the per-node batch contained any
    node-structure-changing action (insert, delete, or move).
    """
    return any(a.action in _STRUCTURAL_ACTIONS for a in batch.actions)


def cleanup_structure_on_move_actions(batch: ActionBatch) -> bool:
    """Run the structural cleanup pass only when the per-node batch contained
    a move_node action. Inserts and deletes alone don't trigger it.
    """
    return any(a.action in _MOVE_ACTIONS for a in batch.actions)
