"""Tests for the actor LLM I/O contract: Pydantic input models, the batch
envelope's lenient filtering, and the input → Action conversion."""

from __future__ import annotations

from prompt_model.actions import (
    ActionBatch,
    AddExampleAction,
    AddExampleInput,
    AddGuidanceAction,
    AddGuidanceInput,
    AddNodeAction,
    DeleteNodeInput,
    InsertNodeInput,
    MoveNodeAction,
    MoveNodeInput,
    RemoveExampleAction,
    RemoveExampleInput,
    RemoveGuidanceAction,
    RemoveGuidanceInput,
    RemoveNodeAction,
    RewriteNodeAction,
    RewriteNodeInput,
    UpdateExampleAction,
    UpdateExampleInput,
    UpdateGuidanceAction,
    UpdateGuidanceInput,
    to_action,
    to_actions,
)

# ---------- per-input → Action conversion ----------


def test_rewrite_node_to_action() -> None:
    action: object = to_action(RewriteNodeInput(action="rewrite_node", id="1.2", text="new"))
    assert isinstance(action, RewriteNodeAction)
    assert action.node_id == "1.2"
    assert action.text == "new"


def test_delete_node_to_action() -> None:
    action: object = to_action(DeleteNodeInput(action="delete_node", id="1.2"))
    assert isinstance(action, RemoveNodeAction)
    assert action.node_id == "1.2"


def test_insert_node_to_action() -> None:
    action: object = to_action(InsertNodeInput(action="insert_node", target="1.2", position="after", subtree="hello"))
    assert isinstance(action, AddNodeAction)
    assert action.subtree_raw == "hello"
    assert action.anchor.target == "1.2"
    assert action.anchor.position == "after"


def test_move_node_to_action() -> None:
    action: object = to_action(MoveNodeInput(action="move_node", id="1.2", target="2.1", position="before"))
    assert isinstance(action, MoveNodeAction)
    assert action.node_id == "1.2"
    assert action.anchor.target == "2.1"
    assert action.anchor.position == "before"


def test_add_example_to_action_no_anchor() -> None:
    action: object = to_action(AddExampleInput(action="add_example", host_id="1.1", text="ex"))
    assert isinstance(action, AddExampleAction)
    assert action.host_id == "1.1"
    assert action.text == "ex"
    assert action.anchor is None


def test_add_example_to_action_with_anchor() -> None:
    action: object = to_action(AddExampleInput(action="add_example", host_id="1.1", text="ex", target="1.1.e1", position="after"))
    assert isinstance(action, AddExampleAction)
    assert action.anchor is not None
    assert action.anchor.target == "1.1.e1"
    assert action.anchor.position == "after"


def test_add_example_target_only_defaults_position_after() -> None:
    """Permissive executor: target without position defaults position to 'after'."""
    action: object = to_action(AddExampleInput(action="add_example", host_id="1.1", text="ex", target="1.1.e1"))
    assert isinstance(action, AddExampleAction)
    assert action.anchor is not None
    assert action.anchor.position == "after"
    assert action.anchor.target == "1.1.e1"


def test_add_example_position_only_drops_anchor() -> None:
    """Permissive executor: position without target ignores both — append at end."""
    action: object = to_action(AddExampleInput(action="add_example", host_id="1.1", text="ex", position="before"))
    assert isinstance(action, AddExampleAction)
    assert action.anchor is None


def test_add_guidance_to_action() -> None:
    action: object = to_action(AddGuidanceInput(action="add_guidance", host_id="1.1", text="be concise"))
    assert isinstance(action, AddGuidanceAction)
    assert action.host_id == "1.1"
    assert action.text == "be concise"


def test_update_example_to_action() -> None:
    action: object = to_action(UpdateExampleInput(action="update_example", id="1.1.e1", text="updated"))
    assert isinstance(action, UpdateExampleAction)
    assert action.annotation_id == "1.1.e1"
    assert action.text == "updated"


def test_update_guidance_to_action() -> None:
    action: object = to_action(UpdateGuidanceInput(action="update_guidance", id="1.1.g1", text="updated"))
    assert isinstance(action, UpdateGuidanceAction)
    assert action.annotation_id == "1.1.g1"


def test_remove_example_to_action() -> None:
    action: object = to_action(RemoveExampleInput(action="remove_example", id="1.1.e1"))
    assert isinstance(action, RemoveExampleAction)
    assert action.annotation_id == "1.1.e1"


def test_remove_guidance_to_action() -> None:
    action: object = to_action(RemoveGuidanceInput(action="remove_guidance", id="1.1.g1"))
    assert isinstance(action, RemoveGuidanceAction)
    assert action.annotation_id == "1.1.g1"


# ---------- ActionBatch parsing ----------


def test_action_batch_parses_well_formed_json() -> None:
    raw = {
        "reasoning": "tighten the intro",
        "actions": [
            {"action": "rewrite_node", "id": "1.1", "text": "new intro"},
            {"action": "add_example", "host_id": "1.1", "text": "a concrete case"},
        ],
    }
    batch: ActionBatch = ActionBatch.model_validate(raw)
    assert batch.reasoning == "tighten the intro"
    assert len(batch.actions) == 2
    assert isinstance(batch.actions[0], RewriteNodeInput)
    assert isinstance(batch.actions[1], AddExampleInput)


def test_action_batch_drops_unknown_action_name() -> None:
    raw = {
        "reasoning": "",
        "actions": [
            {"action": "rewrite_node", "id": "1.1", "text": "good"},
            {"action": "frobnicate", "id": "1.2"},
        ],
    }
    batch: ActionBatch = ActionBatch.model_validate(raw)
    assert len(batch.actions) == 1
    assert isinstance(batch.actions[0], RewriteNodeInput)


def test_action_batch_drops_missing_required_field() -> None:
    raw = {
        "reasoning": "",
        "actions": [
            {"action": "rewrite_node", "id": "1.1"},  # missing text
            {"action": "delete_node", "id": "1.2"},
        ],
    }
    batch: ActionBatch = ActionBatch.model_validate(raw)
    assert len(batch.actions) == 1
    assert isinstance(batch.actions[0], DeleteNodeInput)


def test_action_batch_drops_blank_required_string() -> None:
    raw = {
        "reasoning": "",
        "actions": [
            {"action": "rewrite_node", "id": "1.1", "text": "   "},
        ],
    }
    batch: ActionBatch = ActionBatch.model_validate(raw)
    assert batch.actions == []


def test_action_batch_empty_actions_list_is_valid() -> None:
    raw: dict[str, object] = {"reasoning": "no edits warranted", "actions": []}
    batch: ActionBatch = ActionBatch.model_validate(raw)
    assert batch.actions == []


def test_action_batch_to_actions_round_trip() -> None:
    raw = {
        "reasoning": "",
        "actions": [
            {"action": "rewrite_node", "id": "1.1", "text": "new"},
            {"action": "delete_node", "id": "1.2"},
            {"action": "move_node", "id": "1.3", "target": "2.1", "position": "inside"},
        ],
    }
    batch: ActionBatch = ActionBatch.model_validate(raw)
    actions: list[object] = list(to_actions(batch))
    assert len(actions) == 3
    assert isinstance(actions[0], RewriteNodeAction)
    assert isinstance(actions[1], RemoveNodeAction)
    assert isinstance(actions[2], MoveNodeAction)


def test_action_batch_field_order_in_schema() -> None:
    """reasoning must come before actions in the JSON schema so structured-output
    generation writes the rationale first."""
    schema: dict = ActionBatch.model_json_schema()
    properties: list[str] = list(schema["properties"].keys())
    assert properties.index("reasoning") < properties.index("actions")
