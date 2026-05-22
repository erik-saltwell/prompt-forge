from __future__ import annotations

from pydantic import BaseModel

from .._prompt import Document
from .._prompt.parsing._id_assigner import assign_ids
from .inputs import ActionBatch, to_actions
from .protocol import ApplyContext, SkipReason


class SkippedAction(BaseModel):
    index: int
    reason: SkipReason


class AppliedReport(BaseModel):
    document: Document
    applied: list[int]
    skipped: list[SkippedAction]


def apply_batch(tree: Document, batch: ActionBatch) -> AppliedReport:
    """Apply every action in `batch` to a clone of `tree`, skip-and-continue.

    Frozen-batch-IDs holds: each action resolves against the snapshot's IDs.
    After all actions run, IDs are reassigned once. Returns the new doc plus
    per-action applied/skipped reports.
    """
    clone: Document = tree.model_copy(deep=True)
    ctx: ApplyContext = ApplyContext.from_tree(clone)
    actions = to_actions(batch)
    applied: list[int] = []
    skipped: list[SkippedAction] = []

    for i, action in enumerate(actions):
        reason: SkipReason | None = action.validate(clone)
        if reason is not None:
            skipped.append(SkippedAction(index=i, reason=reason))
            continue
        action.apply(clone, ctx)
        applied.append(i)

    assign_ids(clone)
    return AppliedReport(document=clone, applied=applied, skipped=skipped)
