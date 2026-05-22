from __future__ import annotations

from pydantic import BaseModel

from .._actions.apply_batch import SkippedAction
from .._actions.inputs import ActionBatch
from .._prompt import Document


class ActorResult(BaseModel):
    document: Document
    batch: ActionBatch
    applied: list[int]
    skipped: list[SkippedAction]
