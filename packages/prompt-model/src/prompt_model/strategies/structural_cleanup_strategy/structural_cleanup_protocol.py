from __future__ import annotations

from typing import Protocol

from ..._actions import ActionBatch


class StructuralCleanupDecisionProtocol(Protocol):
    def ShouldCleanup(self, action_batch: ActionBatch) -> bool: ...
