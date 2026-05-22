from __future__ import annotations

from prompt_model._actions import (
    ActionBatch,
    DeleteNodeInput,
    RewriteNodeInput,
    SkipReason,
)
from prompt_model._actions.apply_batch import AppliedReport, apply_batch
from prompt_model._prompt.parsing.parse_prompt import parse_from_string


def test_apply_single_action_returns_mutated_document() -> None:
    tree = parse_from_string("# old\n")
    batch = ActionBatch(reasoning="rename", actions=[RewriteNodeInput(action="rewrite_node", id="1", text="new")])

    report: AppliedReport = apply_batch(tree, batch)

    assert report.document.to_markdown() == "# new\n"
    assert report.applied == [0]
    assert report.skipped == []
    # tree must be re-IDed at end of batch — the root section retains id "1"
    assert report.document.children[0].id == "1"


def test_apply_batch_skips_invalid_action_continues_with_valid() -> None:
    tree = parse_from_string("# a\n\n# b\n")
    batch = ActionBatch(
        reasoning="test skip-and-continue",
        actions=[
            RewriteNodeInput(action="rewrite_node", id="99.99", text="ghost"),  # invalid id
            RewriteNodeInput(action="rewrite_node", id="2", text="bee"),  # valid
        ],
    )

    report: AppliedReport = apply_batch(tree, batch)

    assert report.applied == [1]
    assert len(report.skipped) == 1
    assert report.skipped[0].index == 0
    assert report.skipped[0].reason == SkipReason.TargetNotFound
    assert report.document.to_markdown() == "# a\n\n# bee\n"


def test_frozen_batch_ids_later_action_still_resolves_after_earlier_delete() -> None:
    # Three siblings; delete the first, then rewrite the third by its original id "3".
    # Without frozen-batch-IDs, "3" would have shifted to "2" after the delete and
    # the second action would skip with TargetNotFound. The invariant says it must apply.
    tree = parse_from_string("# a\n\n# b\n\n# c\n")
    batch = ActionBatch(
        reasoning="frozen ids",
        actions=[
            DeleteNodeInput(action="delete_node", id="1"),
            RewriteNodeInput(action="rewrite_node", id="3", text="cee"),
        ],
    )

    report: AppliedReport = apply_batch(tree, batch)

    assert report.applied == [0, 1]
    assert report.skipped == []
    assert report.document.to_markdown() == "# b\n\n# cee\n"
