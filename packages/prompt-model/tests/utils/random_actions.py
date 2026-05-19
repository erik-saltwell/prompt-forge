"""Generate random valid action dicts against a parsed tree.

Produces JSON-shaped action dicts (the form `parse_action` consumes) that
will validate cleanly against the given tree at its current state.
"""

from __future__ import annotations

import random
from collections.abc import Iterator

from prompt_model.model import Annotation, Document, ListItem, Paragraph, PromptNode

_ACTION_KINDS = ("add", "update", "remove")
_ANN_KINDS = ("example", "guidance")


def _walk_hosts(node: PromptNode) -> Iterator[Paragraph | ListItem]:
    if isinstance(node, (Paragraph, ListItem)):
        yield node
    for child in getattr(node, "children", None) or ():
        yield from _walk_hosts(child)


def generate_random_action(tree: Document, rng: random.Random) -> dict | None:
    """Generate a random valid action dict for the given tree's current state.

    Returns the raw JSON form (as `parse_action` consumes), or `None` when
    the tree has no annotatable hosts (no paragraphs or list items).

    Callers driving a sequence should apply each generated action to the
    tree before calling again, so subsequent picks reflect mutations, and
    should pass the same `rng` across calls to keep a single seed reproducible.
    """
    hosts = list(_walk_hosts(tree))
    if not hosts:
        return None

    candidates: list[tuple[str, str]] = [("add", k) for k in _ANN_KINDS]
    existing: dict[str, list[tuple[Paragraph | ListItem, Annotation]]] = {"example": [], "guidance": []}
    for host in hosts:
        if host.examples is not None:
            existing["example"].extend((host, ann) for ann in host.examples.children)
        if host.guidance is not None:
            existing["guidance"].extend((host, ann) for ann in host.guidance.children)
    for ann_kind in _ANN_KINDS:
        if existing[ann_kind]:
            candidates.append(("update", ann_kind))
            candidates.append(("remove", ann_kind))

    action_kind, ann_kind = rng.choice(candidates)
    type_str = f"{action_kind}_{ann_kind}"
    text = f"generated-text-{rng.randint(0, 10**9)}"

    if action_kind == "add":
        host = rng.choice(hosts)
        assert host.id is not None
        group = host.examples if ann_kind == "example" else host.guidance
        anchor_choices: list[dict | None] = [
            None,
            {"first_child": host.id},
            {"last_child": host.id},
        ]
        if group is not None and group.children:
            for ann in group.children:
                assert ann.id is not None
                anchor_choices.append({"before": ann.id})
                anchor_choices.append({"after": ann.id})
        anchor = rng.choice(anchor_choices)
        raw: dict = {"type": type_str, "host_id": host.id, "text": text}
        if anchor is not None:
            raw["anchor"] = anchor
        return raw

    _, ann = rng.choice(existing[ann_kind])
    assert ann.id is not None
    if action_kind == "update":
        return {"type": type_str, "id": ann.id, "text": text}
    return {"type": type_str, "id": ann.id}
