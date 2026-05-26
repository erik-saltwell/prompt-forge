from __future__ import annotations

from enum import StrEnum


class StructuralCleanupOption(StrEnum):
    """Selects when the optional structural cleanup LLM pass runs after the per-node feedback pass."""

    ALWAYS = "always"
    """Always run the structural cleanup pass. Default."""

    NEVER = "never"
    """Never run the structural cleanup pass. Saves one LLM call per bucket."""

    ON_STRUCTURAL_ACTIONS = "on_structural_actions"
    """Run cleanup only when the feedback batch contained ``insert_node``, ``delete_node``, or ``move_node``."""

    ON_MOVE_ACTIONS = "on_move_actions"
    """Run cleanup only when the feedback batch contained ``move_node``. Inserts and deletes alone do not trigger it."""
