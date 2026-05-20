"""Generate random valid action dicts against a parsed tree.

Produces JSON-shaped action dicts (the form `parse_action` consumes) that
will validate cleanly against the given tree at its current state.
"""

from __future__ import annotations

import random

from prompt_model.model import (
    Annotation,
    Blockquote,
    CodeBlock,
    Document,
    ListItem,
    Paragraph,
    PromptNode,
    Section,
    Table,
)
from prompt_model.service.actions import SkipReason, parse_action

_ACTION_KINDS = ("add", "update", "remove")
_ANN_KINDS = ("example", "guidance")

# Max attempts at sampling a valid structural action before giving up on that
# branch for the current call. Each attempt runs a full clone+render+reparse
# validate, so this is the main perf knob. Empirically 8 is plenty — the vast
# majority of randomly-sampled inserts/deletes validate on the first try.
_STRUCTURAL_RETRIES = 8

_Rewritable = Section | Paragraph | ListItem | CodeBlock | Blockquote | Table


def _walk_collect(
    tree: Document,
) -> tuple[
    list[Paragraph | ListItem],
    list[_Rewritable],
    list[PromptNode],
    list[PromptNode],
]:
    """Single-pass traversal collecting every list `generate_random_action`
    needs. Returns (hosts, rewritable, containers, addressable).

    - hosts: nodes that can carry annotations.
    - rewritable: nodes whose text can be rewritten.
    - containers: nodes that accept children (Document + any node with a
      `children` list), used as parents for first_child/last_child inserts.
    - addressable: non-Document nodes with a string id, used as targets for
      before/after inserts and delete_node.
    """
    hosts: list[Paragraph | ListItem] = []
    rewritable: list[_Rewritable] = []
    containers: list[PromptNode] = []
    addressable: list[PromptNode] = []
    stack: list[PromptNode] = [tree]
    while stack:
        node = stack.pop()
        if isinstance(node, (Paragraph, ListItem)):
            hosts.append(node)
        if isinstance(node, (Section, Paragraph, ListItem, CodeBlock, Blockquote, Table)):
            rewritable.append(node)
        if isinstance(node, Document):
            containers.append(node)
        else:
            node_id = getattr(node, "id", None)
            if isinstance(node_id, str):
                addressable.append(node)
                if isinstance(getattr(node, "children", None), list):
                    containers.append(node)
        children = getattr(node, "children", None)
        if children:
            stack.extend(children)
    return hosts, rewritable, containers, addressable


def _validates(raw: dict, tree: Document) -> bool:
    """Build the action from a raw dict and ask it whether it would apply
    cleanly. Used to filter random candidates down to ones the executor
    would accept — keeps the generator from emitting actions the test
    harness would treat as skipped."""
    built = parse_action(raw)
    if isinstance(built, SkipReason):
        return False
    return built.validate(tree) is None


def _sample_structural(
    tree: Document,
    containers: list[PromptNode],
    addressable: list[PromptNode],
    rng: random.Random,
) -> dict | None:
    """Draw a random structural action and return it if it validates.

    Tries up to `_STRUCTURAL_RETRIES` independent samples before giving up.
    Replaces the old `_structural_candidates` enumerate-then-pick approach,
    which validated O(N) candidates per call; here we validate at most
    `_STRUCTURAL_RETRIES`.
    """
    for _ in range(_STRUCTURAL_RETRIES):
        ops: list[str] = []
        if containers:
            ops.append("child_insert")
        if addressable:
            ops.append("sibling_insert")
            ops.append("delete")
        # move needs both a source (any addressable structural node) and a
        # destination anchor (sibling or child of any addressable/container).
        if addressable and (containers or addressable):
            ops.append("move")
        if not ops:
            return None
        op = rng.choice(ops)
        text = f"generated-text-{rng.randint(0, 10**9)}"
        if op == "child_insert":
            parent = rng.choice(containers)
            if isinstance(parent, Document):
                parent_target = ""
            else:
                pid = getattr(parent, "id", None)
                assert isinstance(pid, str)
                parent_target = pid
            kind = rng.choice(("first_child", "last_child"))
            raw: dict = {
                "type": "insert_node",
                "subtree": text,
                "anchor": {kind: parent_target},
            }
        elif op == "sibling_insert":
            target_node = rng.choice(addressable)
            tid = getattr(target_node, "id", None)
            assert isinstance(tid, str)
            kind = rng.choice(("after", "before"))
            raw = {
                "type": "insert_node",
                "subtree": text,
                "anchor": {kind: tid},
            }
        elif op == "delete":
            target_node = rng.choice(addressable)
            tid = getattr(target_node, "id", None)
            assert isinstance(tid, str)
            raw = {"type": "delete_node", "id": tid}
        else:  # move
            source_node = rng.choice(addressable)
            sid = getattr(source_node, "id", None)
            assert isinstance(sid, str)
            anchor_kind = rng.choice(("after", "before", "first_child", "last_child"))
            if anchor_kind in ("after", "before"):
                anchor_target_node = rng.choice(addressable)
                atid = getattr(anchor_target_node, "id", None)
                assert isinstance(atid, str)
                anchor_target = atid
            else:
                parent = rng.choice(containers)
                if isinstance(parent, Document):
                    anchor_target = ""
                else:
                    pid = getattr(parent, "id", None)
                    assert isinstance(pid, str)
                    anchor_target = pid
            raw = {"type": "move_node", "id": sid, "anchor": {anchor_kind: anchor_target}}

        if _validates(raw, tree):
            return raw
    return None


def _random_rewrite_text(node: _Rewritable, rng: random.Random) -> str:
    # Per-node-type rules in rewrite_node.py: Section forbids '\n',
    # Paragraph/ListItem/Blockquote forbid ':::', CodeBlock forbids '```' and
    # ':::', Table requires '|'. The neutral payload below satisfies every
    # type except Table (handled explicitly).
    n = rng.randint(0, 10**9)
    if isinstance(node, Table):
        return f"| col-{n} | val-{n} |"
    return f"generated-text-{n}"


def generate_random_action(tree: Document, rng: random.Random) -> dict | None:
    """Generate a random valid action dict for the given tree's current state.

    Returns the raw JSON form (as `parse_action` consumes), or `None` when
    the tree has no annotatable hosts (no paragraphs or list items).

    Callers driving a sequence should apply each generated action to the
    tree before calling again, so subsequent picks reflect mutations, and
    should pass the same `rng` across calls to keep a single seed reproducible.
    """
    hosts, rewritable, containers, addressable = _walk_collect(tree)
    structural_possible = bool(containers or addressable)
    if not hosts and not rewritable and not structural_possible:
        return None

    # Build candidates without validating structural options. Structural
    # validation is deferred until/unless the "structural" branch is picked,
    # so we don't pay O(N) full-document re-renders per call.
    candidates: list[tuple[str, str]] = []
    if hosts:
        candidates.extend(("add", k) for k in _ANN_KINDS)
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
    if rewritable:
        candidates.append(("rewrite", "node"))
    if structural_possible:
        candidates.append(("structural", "node"))

    # Pick an action kind. If the structural branch fails to find a valid
    # sample within the retry budget, drop it and re-pick from the rest so
    # we still return a usable action when one exists.
    while candidates:
        action_kind, ann_kind = rng.choice(candidates)
        if action_kind != "structural":
            break
        sampled = _sample_structural(tree, containers, addressable, rng)
        if sampled is not None:
            return sampled
        candidates = [c for c in candidates if c[0] != "structural"]
    else:
        return None

    if action_kind == "rewrite":
        node = rng.choice(rewritable)
        assert node.id is not None
        return {"type": "rewrite_node", "id": node.id, "text": _random_rewrite_text(node, rng)}

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
