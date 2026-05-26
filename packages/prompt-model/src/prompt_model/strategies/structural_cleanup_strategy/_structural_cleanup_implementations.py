from ..._actions.inputs import ActionBatch

_STRUCTURAL_ACTIONS: frozenset[str] = frozenset({"insert_node", "delete_node", "move_node"})
_MOVE_ACTIONS: frozenset[str] = frozenset({"move_node"})


class AlwaysCleanup:
    def ShouldCleanup(self, action_batch: ActionBatch) -> bool:
        return True


class NeverCleanup:
    def ShouldCleanup(self, action_batch: ActionBatch) -> bool:
        return False


class CleanupOnStructuralAction:
    def ShouldCleanup(self, action_batch: ActionBatch) -> bool:
        """Run the structural cleanup pass if the per-node batch contained any
        node-structure-changing action (insert, delete, or move).
        """

        return any(a.action in _STRUCTURAL_ACTIONS for a in action_batch.actions)


class CleanupOnMoveAction:
    def ShouldCleanup(self, action_batch: ActionBatch) -> bool:
        """Run the structural cleanup pass only when the per-node batch contained
        a move_node action. Inserts and deletes alone don't trigger it.
        """
        return any(a.action in _MOVE_ACTIONS for a in action_batch.actions)
