"""Actor LLM I/O contract.

Each per-action `*Input` Pydantic class lives next to its action class
(e.g. `RewriteNodeInput` in `rewrite_node.py`). This module assembles them
into the discriminated union, the batch envelope, and the dispatcher.
"""

from __future__ import annotations

from typing import Annotated, cast

from pydantic import BaseModel, Field, TypeAdapter, ValidationError, model_validator

from .add_annotation import AddExampleInput, AddGuidanceInput
from .add_node import InsertNodeInput
from .move_node import MoveNodeInput
from .protocol import Action
from .remove_annotation import RemoveExampleInput, RemoveGuidanceInput
from .remove_node import DeleteNodeInput
from .rewrite_node import RewriteNodeInput
from .update_annotation import UpdateExampleInput, UpdateGuidanceInput

type ActionInput = Annotated[
    RewriteNodeInput
    | DeleteNodeInput
    | InsertNodeInput
    | MoveNodeInput
    | AddExampleInput
    | AddGuidanceInput
    | UpdateExampleInput
    | UpdateGuidanceInput
    | RemoveExampleInput
    | RemoveGuidanceInput,
    Field(discriminator="action"),
]


_ACTION_ADAPTER: TypeAdapter[ActionInput] = TypeAdapter(ActionInput)


class ActionBatch(BaseModel):
    """The structured response returned by one actor LLM call.

    `reasoning` is declared first so structured-output generation produces the
    rationale before the action list, conditioning the actions on it.

    The list is parsed leniently: elements that fail variant validation are
    silently dropped via a pre-validator, so one malformed action does not
    invalidate the whole batch. The schema is still sent to the provider in
    full so constrained generation steers the model toward valid shapes.
    """

    reasoning: str = Field(description="Short rationale for the batch as a whole. Written before the actions to condition them.")
    actions: list[ActionInput] = Field(
        default_factory=list,
        description="Typed action list. Each element conforms to the schema for its `action` tag.",
    )

    @model_validator(mode="before")
    @classmethod
    def _drop_invalid_actions(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        data_dict: dict[str, object] = cast(dict[str, object], data)
        raw_actions: object = data_dict.get("actions")
        if not isinstance(raw_actions, list):
            return data_dict
        kept: list[object] = []
        for elem in raw_actions:
            try:
                _ACTION_ADAPTER.validate_python(elem)
            except ValidationError:
                continue
            kept.append(elem)
        return {**data_dict, "actions": kept}


def to_action(input: ActionInput) -> Action:
    """Convert a typed LLM input model into its corresponding executable Action.

    Dispatch lives on each input class as a `to_action()` method; this function
    is a thin facade for callers that prefer free-function style.
    """
    return input.to_action()


def to_actions(batch: ActionBatch) -> list[Action]:
    """Convert every input in a batch to its executable Action, preserving order."""
    return [item.to_action() for item in batch.actions]
